import importlib.util,sys
from pathlib import Path
from sqlalchemy import text
from test_cafe_wallet import env,fund

def reports():
    spec=importlib.util.spec_from_file_location('app.services.cafe_audit_reports',Path(__file__).parents[1]/'app/services/cafe_audit_reports.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_topup_and_collection_are_visible_once_with_credit_movement(env):
    e=env
    with e.app.app_context():
        import pytest
        if not e.pg:pytest.skip('Audit SQL uses PostgreSQL')
        fund(e,amount=10000)
        for name,kind in [('booking_date','date'),('booking_time','time'),('mode_of_payment','text'),('initiated_by_staff_name','text')]:e.db.session.execute(text(f'ALTER TABLE transactions ADD COLUMN {name} {kind}'))
        report=reports().ledger_report(1,{})
        assert report['total']==1 and report['items'][0]['kind']=='topup'
        assert report['items'][0]['amount_paise']==10000
        assert report['items'][0]['balance_after_paise']==10000
        assert reports().ledger_report(2,{})['total']==0
        assert reports().ledger_report(1,{'kind':'session_collection'})['total']==0
        e.s.ledger(e.db.session.get(e.m.CafeWallet,(1,1)),'session_collection',10000,{'id':'owner','name':'Owner'},'report-collection-key','report-fingerprint',method='cash',session_id='test-session',reason='Desk extension collected')
        e.db.session.commit()
        page=reports().ledger_report(1,{'limit':'1'})
        assert page['total']==2 and len(page['items'])==1
        second=reports().ledger_report(1,{'limit':'1','page':'2'})
        assert page['items'][0]['id']!=second['items'][0]['id']

def test_console_history_includes_qr_actual_session_and_blocks_other_cafe(env):
    e=env
    with e.app.app_context():
        import pytest
        if not e.pg:pytest.skip('Audit SQL uses PostgreSQL')
        e.db.session.execute(text('ALTER TABLE vendor_1_dashboard ADD COLUMN username text'));e.db.session.commit()
        fund(e)
        qr=e.s.reserve(1,1,e.db.session.get(e.Link,1),60,'audit-history-session')
        e.db.session.commit();e.s.acknowledge(qr.id,e.db.session.get(e.Link,1),qr.command_token,True);e.db.session.commit()
        result=reports().console_history(1,1,{})
        assert result['total']==1 and result['items'][0]['reference']==qr.id
        assert result['items'][0]['time_basis']=='actual start / scheduled end'
        import pytest
        with pytest.raises(e.s.CafeError):reports().console_history(2,1,{})


def test_credit_movement_and_runtime_history_do_not_duplicate_qr(env):
    e=env
    with e.app.app_context():
        import pytest
        if not e.pg:pytest.skip('Audit SQL uses PostgreSQL')
        from test_session_extensions import active,extend,engine
        for name,kind in [('booking_date','date'),('booking_time','time'),('mode_of_payment','text'),('initiated_by_staff_name','text')]:e.db.session.execute(text(f'ALTER TABLE transactions ADD COLUMN {name} {kind}'))
        e.db.session.execute(text('ALTER TABLE vendor_1_dashboard ADD COLUMN username text'));e.db.session.commit()
        row,qr=active(e)
        w=e.db.session.get(e.m.CafeWallet,(1,1));w.balance=0;e.db.session.commit()
        q,_=extend(e,row);c=engine();part=c.segments(row)[0]
        c.accrue(row,part.starts_at+(part.ends_at-part.starts_at)/2);e.db.session.commit()
        journal=reports().ledger_report(1,{'kind':'credit_charge'})
        assert journal['total']==1 and journal['items'][0]['amount_paise']==part.credit_due
        assert journal['items'][0]['category']=='credit_debt'
        history=reports().console_history(1,1,{})
        assert history['total']==1 and history['items'][0]['source']=='self_qr'
        assert history['items'][0]['extension_due_paise']==part.credit_due
        assert history['items'][0]['reference']==qr.id


def test_report_filters_validate_ranges(env):
    e=env
    with e.app.app_context():
        import pytest
        with pytest.raises(e.s.CafeError):reports().bounds({'from':'2026-10-10','to':'2026-10-01'})
        with pytest.raises(e.s.CafeError):reports().bounds({'page':'0'})
        with pytest.raises(e.s.CafeError):reports().bounds({'limit':'101'})
