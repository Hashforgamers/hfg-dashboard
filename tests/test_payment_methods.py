"""Exercise the production payment-settings handlers in a disposable DB."""
import ast
from pathlib import Path
from datetime import datetime
import types
import pytest
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import text
from test_cafe_wallet import env, staff_token, auth

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def methods(env):
    e=env;db=e.db
    if not e.pg:pytest.skip("PostgreSQL settings SQL")
    class PaymentMethod(db.Model):
        __tablename__='payment_method'
        pay_method_id=db.Column(db.Integer,primary_key=True)
        method_name=db.Column(db.String,unique=True)
    class PaymentVendorMap(db.Model):
        __tablename__='payment_vendor_map'
        id=db.Column(db.Integer,primary_key=True)
        vendor_id=db.Column(db.Integer)
        pay_method_id=db.Column(db.Integer)
    Vendor=db.Model.registry._class_registry['Vendor']
    blueprint=Blueprint('payment_test',__name__)
    names={'_normalize_payment_method_name','_ensure_payment_method_catalog','_method_ids_for_canonical','_set_vendor_payment_method_state','_sync_cafe_specific_pass_payment_method','_build_payment_method_response','get_all_payment_methods_for_vendor','toggle_payment_method_for_vendor'}
    nodes=[]
    for n in ast.parse((ROOT/'app/routes.py').read_text()).body:
        if isinstance(n,ast.FunctionDef) and n.name in names:nodes.append(n)
        elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYMENT_METHOD_DEFINITIONS' for t in n.targets):nodes.append(n)
    scope=dict(db=db,PaymentMethod=PaymentMethod,PaymentVendorMap=PaymentVendorMap,Vendor=Vendor,dashboard_service=blueprint,jsonify=jsonify,request=request,current_app=current_app)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/'app/routes.py'),'exec'),scope)
    e.app.register_blueprint(blueprint,url_prefix='/api')
    with e.app.app_context():
        db.session.execute(text("SELECT setval(pg_get_serial_sequence('payment_method','pay_method_id'),6)"));db.session.commit()
    yield e


def test_all_six_methods_and_authenticated_idempotent_selection(methods):
    e=methods;c=e.app.test_client();path='/api/vendor/1/paymentMethods'
    result=c.get(path).json
    assert len(result['payment_methods'])==6
    assert {m['method_name'] for m in result['payment_methods']}=={'hash_wallet','cafe_wallet','hash_global_pass','cafe_specific_pass','payment_gateway','pay_at_cafe'}
    change={'pay_method_id':1,'is_enabled':False}
    assert c.post(path+'/toggle',json=change).status_code==401
    owner=staff_token(e,'owner')
    assert c.post('/api/vendor/2/paymentMethods/toggle',json=change,headers=auth(owner)).status_code==403
    for _ in range(2):
        response=c.post(path+'/toggle',json=change,headers=auth(owner))
        assert response.status_code==200,response.json
        assert response.json['data']['is_enabled'] is False
    state={m['method_name']:m['is_enabled'] for m in c.get(path).json['payment_methods']}
    assert not state['cafe_wallet'] and state['payment_gateway']
    for _ in range(2):
        response=c.post(path+'/toggle',json=dict(change,is_enabled=True),headers=auth(owner))
        assert response.status_code==200,response.json
    assert c.post(path+'/toggle',json=dict(change,is_enabled='false'),headers=auth(owner)).status_code==400


def test_migration_rerun_preserves_disabled_method(env):
    e=env
    if not e.pg:pytest.skip('PostgreSQL migration')
    with e.app.app_context():
        e.db.session.execute(text('CREATE TABLE cafe_passes(vendor_id integer,is_active boolean)'))
        e.db.session.commit()
        raw=e.db.engine.raw_connection()
        try:
            cursor=raw.cursor()
            cursor.execute("SELECT setval(pg_get_serial_sequence('payment_method','pay_method_id'),6)")
            cursor.execute((ROOT/'sql/20260929_payment_methods.sql').read_text());raw.commit()
            cursor.execute('DELETE FROM payment_vendor_map WHERE vendor_id=1 AND pay_method_id=3');raw.commit()
            cursor.execute((ROOT/'sql/20260929_payment_methods.sql').read_text());raw.commit()
            cursor.execute('SELECT count(*) FROM payment_vendor_map WHERE vendor_id=1 AND pay_method_id=3')
            assert cursor.fetchone()[0]==0
        finally:raw.close()
