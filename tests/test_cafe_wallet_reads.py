"""Gamer wallet reads: tenant isolation, safe projection and cursor boundaries."""
from datetime import datetime, timedelta

import jwt
import pytest

from test_cafe_wallet import env, auth, gamer, fund, staff_token


def test_balances_are_private_paginated_and_do_not_create_wallets(env):
    e = env
    client = e.app.test_client()
    with e.app.app_context():
        fund(e)
        e.db.session.add_all([
            e.m.CafeWallet(vendor_id=2, user_id=1, balance=0, reserved=0),
            e.m.CafeWallet(vendor_id=1, user_id=2, balance=99000, reserved=0),
        ])
        e.db.session.get(e.m.CafeWallet, (1, 1)).reserved = 5000
        e.db.session.commit()
    headers = auth(gamer(e))
    response = client.get('/api/cafe/wallets?limit=1&user_id=2', headers=headers)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'
    first = response.json
    assert first['next_cursor'] == 1
    assert first['items'] == [dict(vendor_id=1, cafe_name='Test Cafe', currency='INR',
        balance=20000, reserved=5000, available_balance=15000, topup_at_cafe_only=True)]
    second = client.get('/api/cafe/wallets?limit=1&after=1', headers=headers).json
    assert second['next_cursor'] is None
    assert [item['vendor_id'] for item in second['items']] == [2]
    balance = client.get('/api/cafe/1/wallet?user_id=2', headers=headers)
    assert balance.json == first['items'][0]
    assert balance.headers['Cache-Control'] == 'private, no-store'
    # A valid cafe with no wallet is a zero balance; GET must not insert a row.
    empty = client.get('/api/cafe/2/wallet', headers=auth(gamer(e, 2)))
    assert empty.status_code == 200 and empty.json['balance'] == 0
    assert client.get('/api/cafe/2/wallet/history', headers=auth(gamer(e, 2))).json['items'] == []
    assert client.get('/api/cafe/999/wallet', headers=headers).status_code == 404
    assert client.get('/api/cafe/999/wallet/history', headers=headers).status_code == 404
    with e.app.app_context():
        assert e.m.CafeWallet.query.count() == 3
        assert e.m.CafeLedger.query.count() == 1


def test_history_is_scoped_filtered_and_stably_paginated(env):
    e = env
    def add(kind, amount, vendor=1, user=1):
        row = e.m.CafeLedger(vendor_id=vendor, user_id=user, kind=kind, amount=amount,
            balance_after=20000, reserved_after=0, actor_id='staff-secret', actor_name='Private name',
            reason='Internal note', idempotency_key=f'{vendor}-{user}-{kind}', fingerprint='secret')
        e.db.session.add(row)
        e.db.session.flush()
        return row.id
    with e.app.app_context():
        expected = [add('topup', 20000), add('reserve', 0), add('capture', -10000),
                    add('release', 0), add('adjustment', 1000), add('refund', 10000)]
        add('food_collection', 5000)
        add('topup', 80000, user=2)
        add('topup', 90000, vendor=2)
        e.db.session.commit()
    client = e.app.test_client()
    headers = auth(gamer(e))
    response = client.get('/api/cafe/1/wallet/history?limit=2&user_id=2', headers=headers)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'
    page = response.json
    assert page['vendor_id'] == 1 and page['currency'] == 'INR'
    assert set(page['items'][0]) == {'id', 'kind', 'amount', 'balance_after', 'reserved_after',
                                    'method', 'session_id', 'reversal_of', 'created_at'}
    assert page['items'][0]['created_at'].endswith('Z')
    ids = [item['id'] for item in page['items']]
    # New entries arriving between pages must not duplicate or shift old results.
    with e.app.app_context():
        add('reserve', 0, vendor=2)
        e.db.session.add(e.m.CafeLedger(vendor_id=1, user_id=1, kind='topup', amount=1000,
            balance_after=21000, reserved_after=0, actor_id='1', actor_name='Sam',
            reason='new', idempotency_key='new-topup', fingerprint='new'))
        e.db.session.commit()
    while page['next_cursor'] is not None:
        page = client.get(f"/api/cafe/1/wallet/history?limit=2&before={page['next_cursor']}", headers=headers).json
        ids.extend(item['id'] for item in page['items'])
    assert ids == list(reversed(expected))


@pytest.mark.parametrize('path', ['/api/cafe/wallets', '/api/cafe/1/wallet', '/api/cafe/1/wallet/history'])
def test_wallet_reads_reject_missing_staff_expired_and_wrong_audience_tokens(env, path):
    e = env
    client = e.app.test_client()
    now = datetime.utcnow()
    claims = dict(sub='1', aud='cafe-checkout', scope='cafe_gamer', iat=now, exp=now+timedelta(minutes=5))
    invalid = [staff_token(e), 'not-a-token']
    for changes in [dict(exp=now-timedelta(seconds=1)), dict(aud='other'), dict(scope='vendor_access')]:
        invalid.append(jwt.encode(dict(claims, **changes), e.app.config['JWT_SECRET_KEY'], algorithm='HS256'))
    assert client.get(path).status_code == 401
    for token in invalid:
        assert client.get(path, headers=auth(token)).status_code == 401


@pytest.mark.parametrize('path', ['/api/cafe/wallets', '/api/cafe/1/wallet/history'])
@pytest.mark.parametrize('value', ['0', '-1', '101', 'abc', '1.5', '', '999999999999999999'])
def test_invalid_limits_are_rejected(env, path, value):
    assert env.app.test_client().get(f'{path}?limit={value}', headers=auth(gamer(env))).status_code == 400


@pytest.mark.parametrize('path,cursor', [('/api/cafe/wallets', 'after'), ('/api/cafe/1/wallet/history', 'before')])
def test_cursor_validation_and_empty_pages(env, path, cursor):
    client = env.app.test_client()
    headers = auth(gamer(env))
    for value in ['0', '-1', 'bad', '1.2', '2147483648']:
        assert client.get(f'{path}?{cursor}={value}', headers=headers).status_code == 400
    assert client.get(path, headers=headers).json['items'] == []
    assert client.get(path, headers=headers).json['next_cursor'] is None


def test_gamer_cannot_use_staff_topup_or_wallet_routes(env):
    client = env.app.test_client()
    headers = auth(gamer(env))
    assert client.get('/api/cafe/1/wallets/1', headers=headers).status_code in (401, 403, 422)
    assert client.post('/api/cafe/1/wallets/1/topups', headers=headers,
        json={'amount': 10000, 'method': 'cash', 'idempotency_key': 'app-topup-attempt'}).status_code in (401, 403, 422)
    with env.app.app_context():
        assert env.m.CafeWallet.query.count() == 0
        assert env.m.CafeLedger.query.count() == 0


def test_topup_search_contact_privacy_and_customer_scope(env):
    from sqlalchemy import text
    from app.models.user import User
    from app.models.contactInfo import ContactInfo
    e = env
    with e.app.app_context():
        e.db.session.get(User,1).name = 'Asha Rao'
        e.db.session.add(ContactInfo(parent_id=1,parent_type='user',email='asha@example.test',phone='9876543210'))
        e.db.session.execute(text("INSERT INTO transactions(id,vendor_id,user_id,settlement_status) VALUES(1,2,1,'completed')"))
        e.db.session.add(e.m.CafeWallet(vendor_id=1,user_id=1,balance=0,reserved=0))
        e.db.session.commit()
        token = staff_token(e,role='owner')
    client = e.app.test_client()
    response = client.get('/api/cafe/1/gamers?q=Asha',headers=auth(token))
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'
    row = response.json[0]
    assert row['phone'] == '******210' and row['email'] == 'as***@example.test'
    assert row['contact_masked'] is True and row['is_cafe_customer'] is False
    assert '9876543210' not in response.get_data(as_text=True)
    assert 'asha@example.test' not in response.get_data(as_text=True)
    with e.app.app_context():
        e.db.session.execute(text("INSERT INTO transactions(id,vendor_id,user_id,settlement_status) VALUES(2,1,1,'completed')"))
        e.db.session.commit()
    row = client.get('/api/cafe/1/gamers?q=Asha',headers=auth(token)).json[0]
    assert row['phone'] == '9876543210' and row['email'] == 'asha@example.test'
    assert row['contact_masked'] is False and row['is_cafe_customer'] is True


def test_topup_establishes_customer_contact_access(env):
    from app.models.user import User
    from app.models.contactInfo import ContactInfo
    e = env
    with e.app.app_context():
        e.db.session.get(User,1).name = 'Asha'
        e.db.session.add(ContactInfo(parent_id=1,parent_type='user',email='asha@example.test',phone='9876543210'))
        fund(e)
        e.db.session.commit()
        token = staff_token(e,role='owner')
    row = e.app.test_client().get('/api/cafe/1/gamers?q=Asha',headers=auth(token)).json[0]
    assert row['phone']=='9876543210' and row['contact_masked'] is False
