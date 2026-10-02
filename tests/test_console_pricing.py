"""Pricing and real wallet quote/reservation/capture regression tests."""
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import types
import ast
import pytest
from sqlalchemy import text
from test_cafe_wallet import env, fund, ACTOR, staff_token, auth

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pricing_math_test',ROOT/'app/services/pricing_math.py')
math=importlib.util.module_from_spec(spec);spec.loader.exec_module(math)

def offer(start,end,price):
    return SimpleNamespace(start_date=start.date(),start_time=start.time(),end_date=end.date(),end_time=end.time(),offered_price=price,is_active=True)

def test_independently_deployed_services_share_pricing_contract():
    booking_copy=ROOT.parent/'hfg-booking/services/pricing_math.py'
    if not booking_copy.exists():pytest.skip('Sibling booking checkout is unavailable')
    assert (ROOT/'app/services/pricing_math.py').read_bytes()==booking_copy.read_bytes()

@pytest.mark.parametrize('value',[True,-1,'NaN','Infinity','1.001','wrong'])
def test_invalid_prices_rejected(value):
    with pytest.raises(ValueError):math.money(value)

def test_offer_window_midnight_boundaries_lowest_price_and_lowered_base():
    start=datetime(2026,10,1,23,30);end=start+timedelta(hours=1)
    promos=[offer(start,end,80),offer(start,end,60)]
    assert math.effective_price(100,promos,start,end)==60
    assert math.effective_price(50,promos,start,end)==50
    assert math.effective_price(100,[offer(start,end-timedelta(minutes=1),20)],start,end)==100
    assert math.slot_window(start.date(),time(23,30),time(0,30))==(start,end)

def test_wallet_prorates_console_slots_and_covered_offers():
    slots=[SimpleNamespace(start_time=time(10),end_time=time(10,30)),SimpleNamespace(start_time=time(10,30),end_time=time(11))]
    start=datetime(2026,10,1,10,15)
    assert math.session_amount(50,slots,[],start,30)==5000
    promos=[offer(datetime(2026,10,1,10),datetime(2026,10,1,10,30),30)]
    assert math.session_amount(50,slots,promos,start,30)==4000
    with pytest.raises(ValueError,match='cover'):math.session_amount(50,slots,[],start,60)
    with pytest.raises(ValueError,match='overlap'):math.session_amount(50,slots+slots,[],start,30)

def test_controller_bundle_composition_and_quantity_limits():
    assert math.controller_total('40',[{'quantity':2,'total_price':'60'}],5)==160
    assert math.controller_total('10.25',[],3)==Decimal('30.75')
    for quantity in [True,-1,1.5,65]:
        with pytest.raises(ValueError):math.controller_total(10,[],quantity)

def test_duration_policy_strips_legacy_price_override(env):
    settings=dict(env.s.DEFAULT_POLICY,durations=[{'minutes':60,'amount':1}])
    assert env.s.validate_policy(settings)['durations']==[{'minutes':60}]
    for durations in [[{'minutes':0}],[{'minutes':60},{'minutes':60}],[{'minutes':60.5}]]:
        with pytest.raises(env.s.CafeError):env.s.validate_policy(dict(settings,durations=durations))

def test_console_price_drives_quote_reservation_and_capture(env):
    e=env
    with e.app.app_context():
        fund(e)
        link=e.db.session.get(e.Link,1)
        e.db.session.execute(text('UPDATE available_games SET single_slot_price=75 WHERE id=100'));e.db.session.commit()
        details=e.c.checkout_details(link,1)
        assert details['policy']['durations']==[{'minutes':60,'amount':15000}]
        with pytest.raises(e.s.CafeError,match='Price changed'):e.s.reserve(1,1,link,60,'old-price-request',expected_amount=10000)
        e.db.session.rollback()
        session=e.s.reserve(1,1,link,60,'new-price-request',expected_amount=15000);e.db.session.commit()
        assert session.amount==15000
        assert e.m.CafeWallet.query.one().reserved==15000
        # Configuration changes after reserve do not alter the accepted amount.
        e.db.session.execute(text('UPDATE available_games SET single_slot_price=100 WHERE id=100'));e.db.session.commit()
        e.s.acknowledge(session.id,link,session.command_token,True);e.db.session.commit()
        assert e.m.CafeWallet.query.one().balance==5000
        assert e.m.CafeLedger.query.filter_by(kind='capture').one().amount==-15000

def test_unknown_console_price_cannot_debit_and_existing_balance_stays_visible(env):
    e=env
    with e.app.app_context():
        fund(e);link=e.db.session.get(e.Link,1)
        e.db.session.execute(text('DELETE FROM available_game_console'));e.db.session.commit()
        result=e.c.checkout_details(link,1)
        assert result['pricing_error'] and result['available_balance']==20000
        with pytest.raises(e.s.CafeError,match='exactly one'):e.s.reserve(1,1,link,60,'unmapped-console')
        e.db.session.rollback()
        assert e.m.CafeWallet.query.one().reserved==0

@pytest.fixture
def pricing_api(env,monkeypatch):
    e=env;db=e.db
    if not e.pg:pytest.skip('PostgreSQL integration')
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules,name,module);spec.loader.exec_module(module);return module
    class AvailableGame(db.Model):
        __tablename__='available_games'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        game_name=db.Column(db.String)
        single_slot_price=db.Column(db.Integer)
    module=types.ModuleType('app.models.availableGame');module.AvailableGame=AvailableGame;monkeypatch.setitem(sys.modules,module.__name__,module)
    for name in ['consolePricingOffer','controllerPricingRule','controllerPricingTier','squadPricingRule']:
        load('app.models.'+name,'app/models/'+name+'.py')
    catalog=types.ModuleType('app.services.console_catalog_service')
    catalog.normalize_console_slug=lambda value:'pc' if 'pc' in str(value).lower() else str(value).lower()
    catalog.legacy_console_group=lambda value,capabilities=None:catalog.normalize_console_slug(value)
    catalog.resolve_console_capabilities=lambda **kw:dict(slug=catalog.normalize_console_slug(kw['raw_console']),supports_multiplayer=True,default_capacity=10,controller_policy='none' if 'pc' in kw['raw_console'].lower() else 'controller_pricing')
    monkeypatch.setitem(sys.modules,catalog.__name__,catalog)
    controller=load('app.controllers.pricingController','app/controllers/pricingController.py')
    guard=load('app.middleware.rbac_guard','app/middleware/rbac_guard.py')
    e.app.before_request(guard.enforce_rbac_permissions)
    e.app.register_blueprint(controller.pricing_blueprint,url_prefix='/api')
    with e.app.app_context():
        db.create_all()
        db.session.execute(text("INSERT INTO available_games VALUES(101,1,'playstation',80)"));db.session.commit()
    # Execute the real base-price endpoint without importing unrelated route integrations.
    from flask import request, jsonify, current_app
    tree=ast.parse((ROOT/'app/routes.py').read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='update_console_pricing')
    node.decorator_list=[]
    namespace=dict(Vendor=controller.Vendor,AvailableGame=AvailableGame,db=db,request=request,jsonify=jsonify,
                   current_app=current_app,normalize_console_slug=catalog.normalize_console_slug,
                   socketio=SimpleNamespace(emit=lambda *a,**kw:None))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'app/routes.py','exec'),namespace)
    e.app.add_url_rule('/vendor/<int:vendor_id>/console-pricing',view_func=namespace['update_console_pricing'],methods=['POST'])
    e.pricing=controller
    yield e


def test_offer_create_update_overlap_validation_and_permissions(pricing_api):
    e=pricing_api;c=e.app.test_client();url='/api/vendor/1/pricing-offers';headers=auth(staff_token(e,'owner'))
    body=dict(available_game_id=100,offered_price=30,start_date='2026-10-01',start_time='10:00',end_date='2026-10-01',end_time='11:00',offer_name='Morning')
    assert c.post(url,json=body).status_code==401
    assert c.post(url,json=body,headers=auth(staff_token(e,'staff'))).status_code==403
    first=c.post(url,json=body,headers=headers)
    assert first.status_code==201,first.json
    second=c.post(url,json=dict(body,start_time='11:00',end_time='12:00'),headers=headers)
    assert second.status_code==201,second.json
    target=f'{url}/{second.json["offer"]["id"]}'
    assert c.put(target,json={'start_time':'10:30'},headers=headers).status_code==400
    assert c.put(target,json={'end_time':'09:00'},headers=headers).status_code==400
    assert c.put(target,json={'is_active':'false'},headers=headers).status_code==400
    assert c.put(target,json={'offered_price':'NaN'},headers=headers).status_code==400
    assert c.put(target,json={'is_active':False},headers=headers).status_code==200
    assert c.post(url,json=dict(body,offered_price=30.001),headers=headers).status_code==400


def test_controller_save_calculate_reject_invalid_and_squad_defaults(pricing_api):
    e=pricing_api;c=e.app.test_client();headers=auth(staff_token(e,'owner'));url='/api/vendor/1/controller-pricing'
    body={'pricing':{'playstation':{'base_price':40,'tiers':[{'quantity':2,'total_price':60}]}}}
    assert c.put(url,json=body,headers=headers).status_code==200
    quote=c.get(url+'/calculate?console_type=playstation&quantity=5')
    assert quote.status_code==200 and quote.json['total_price']==160,quote.json
    assert c.get(url+'/calculate?console_type=playstation&quantity=100000000').status_code==400
    body['pricing']['playstation']['tiers'][0]['quantity']=2.5
    assert c.put(url,json=body,headers=headers).status_code==400
    squad='/api/vendor/1/squad-pricing-rules'
    assert c.put(squad,json={'pricing':{'pc':{'2':0,'3':'NaN'}}},headers=headers).status_code==400
    assert c.put(squad,json={'pricing':{'pc':{'2':0,'3':5}}},headers=headers).status_code==200
    state=c.get(squad).json['pricing']
    assert state['pc']['3']==5 and state['pc']['4']==0


def test_base_price_api_updates_wallet_quote_and_rejects_invalid(pricing_api):
    e=pricing_api;c=e.app.test_client();headers=auth(staff_token(e,'owner'))
    url='/vendor/1/console-pricing'
    for value in [-1,True,50.5,'NaN','Infinity',10001]:
        assert c.post(url,json={'pc':value},headers=headers).status_code==400
    assert c.post(url,json={'unknown':75},headers=headers).status_code==400
    assert c.post(url,json={'pc':75},headers=headers).status_code==200
    with e.app.app_context():
        quote=e.c.checkout_details(e.db.session.get(e.Link,1),1)
        assert quote['policy']['durations']==[{'minutes':60,'amount':15000}]


def test_malformed_controller_rule_is_client_error(pricing_api):
    e=pricing_api
    response=e.app.test_client().put('/api/vendor/1/controller-pricing',json={'pricing':{'playstation':5}},headers=auth(staff_token(e,'owner')))
    assert response.status_code==400


def test_qr_quote_uses_dated_schedule_and_ignores_other_templates(env):
    from app.services.cafe_session_pricing import session_prices
    e = env
    with e.app.app_context():
        day = date(2026, 10, 2)
        e.db.session.execute(text('DELETE FROM vendor_1_slot'))
        # A different day's hour-long slot and an unused historical template
        # must not overlap Friday's half-hour schedule.
        e.db.session.execute(text('INSERT INTO slots VALUES (200,100,:start,:end),(201,100,:start,:end)'),
            {'start': time(10), 'end': time(11)})
        for slot_id, scheduled_day in [(120,day),(121,day),(120,day),(200,day-timedelta(days=1))]:
            e.db.session.execute(text('INSERT INTO vendor_1_slot VALUES (1,:id,:day)'),
                {'id':slot_id, 'day':scheduled_day})
        link = e.db.session.get(e.Link, 1)
        result = session_prices(link, [{'minutes':30},{'minutes':60}], datetime.combine(day,time(10,15)))
        assert result[0] == {'minutes':30, 'amount':5000}
        assert result[1]['amount'] is None
        assert 'cover' in result[1]['unavailable_reason']


def test_dated_session_slots_cover_midnight_without_repeating_previous_day():
    day = date(2026, 10, 2)
    slots = [SimpleNamespace(date=day,start_time=time(23,30),end_time=time(0)),
             SimpleNamespace(date=day+timedelta(days=1),start_time=time(0),end_time=time(0,30)),
             SimpleNamespace(date=day-timedelta(days=1),start_time=time(0),end_time=time(1))]
    assert math.session_amount(50,slots,[],datetime.combine(day,time(23,45)),30) == 5000
    with pytest.raises(ValueError,match='cover'):
        math.session_amount(50,slots[:1],[],datetime.combine(day,time(23,45)),30)
