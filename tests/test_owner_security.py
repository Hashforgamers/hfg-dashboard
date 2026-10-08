from unittest.mock import Mock
import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import text
from test_subscription_commerce import commerce
from test_subscription_checkout import app,db
from app.controllers.access_controller import bp_access

@pytest.fixture
def security(commerce,monkeypatch):
    from app.controllers import cafe_wallet_controller
    from app.services import cafe_wallet_service
    from flask_jwt_extended import JWTManager
    from app.controllers.cafe_wallet_controller import cafe_error
    from app.services.cafe_wallet_service import CafeError
    JWTManager(commerce)
    commerce.register_error_handler(CafeError,cafe_error)
    commerce.register_blueprint(bp_access)
    monkeypatch.setattr(cafe_wallet_service,'audit',Mock())
    db.session.execute(text('CREATE TABLE password_manager(id integer PRIMARY KEY,parent_id integer,parent_type text,password text,must_change_password boolean)'))
    db.session.execute(text('CREATE TABLE vendor_pins(id '+('serial' if db.engine.dialect.name=='postgresql' else 'integer')+' PRIMARY KEY,vendor_id integer,pin_code text UNIQUE)'))
    from app.models.vendorStaff import VendorStaff
    from app.models.cafe_wallet import CafeStaffSession
    from app.models.vendorRolePermission import VendorRolePermission
    for model in [VendorStaff,CafeStaffSession,VendorRolePermission]:model.__table__.create(db.engine,checkfirst=True)
    db.session.execute(text("INSERT INTO password_manager VALUES(1,1,'vendor','OldPassword123',false)"));db.session.commit()
    return commerce

def change(a,body,role='owner'):
    token=create_access_token(identity='owner-1',additional_claims={'scope':'vendor_access','vendor_id':1,'staff':{'id':'owner-1','role':role,'name':'Owner'}})
    from flask_jwt_extended import decode_token
    from datetime import datetime,timedelta
    from app.models.cafe_wallet import CafeStaffSession
    db.session.add(CafeStaffSession(jti=decode_token(token)['jti'],vendor_id=1,actor_id='owner-1',actor_name='Owner',expires_at=datetime.utcnow()+timedelta(minutes=10)))
    db.session.commit()
    return a.test_client().post('/api/vendor/1/access/owner/security',json=body,headers={'Authorization':'Bearer '+token})

def test_owner_password_requires_current_password(security):
    body={'kind':'password','current_password':'wrong','new_value':'NewPassword123','confirm_value':'NewPassword123'}
    assert change(security,body).status_code==400
    assert db.session.execute(text('SELECT password FROM password_manager')).scalar()=='OldPassword123'
    body['current_password']='OldPassword123'
    assert change(security,body).status_code==200
    assert db.session.execute(text('SELECT password FROM password_manager')).scalar()=='NewPassword123'

def test_staff_cannot_change_owner_security(security):
    body={'kind':'pin','current_password':'OldPassword123','new_value':'1234','confirm_value':'1234'}
    assert change(security,body,'manager').status_code==403
    assert db.session.execute(text('SELECT count(*) FROM vendor_pins')).scalar()==0

def test_pin_confirmation_validation_and_success(security):
    body={'kind':'pin','current_password':'OldPassword123','new_value':'1234','confirm_value':'9999'}
    assert change(security,body).status_code==400
    body.update(new_value='12345',confirm_value='12345');assert change(security,body).status_code==400
    body.update(new_value='4837',confirm_value='4837');assert change(security,body).status_code==200
    assert db.session.execute(text('SELECT pin_code FROM vendor_pins WHERE vendor_id=1')).scalar()=='4837'


def test_closed_owner_session_cannot_change_credentials(security):
    from app.models.cafe_wallet import CafeStaffSession
    from flask_jwt_extended import decode_token
    from datetime import datetime,timedelta
    token=create_access_token(identity='owner-1',additional_claims={'scope':'vendor_access','vendor_id':1,'staff':{'id':'owner-1','role':'owner','name':'Owner'}})
    db.session.add(CafeStaffSession(jti=decode_token(token)['jti'],vendor_id=1,actor_id='owner-1',actor_name='Owner',expires_at=datetime.utcnow()+timedelta(minutes=10),closed_at=datetime.utcnow()));db.session.commit()
    response=security.test_client().post('/api/vendor/1/access/owner/security',json={'kind':'pin','current_password':'OldPassword123','new_value':'4837','confirm_value':'4837'},headers={'Authorization':'Bearer '+token})
    assert response.status_code==401

def test_existing_pin_is_rotated_without_creating_duplicate(security):
    db.session.execute(text("INSERT INTO vendor_pins(vendor_id,pin_code) VALUES(1,'4837')"));db.session.commit()
    assert change(security,{'kind':'pin','current_password':'OldPassword123','new_value':'0007','confirm_value':'0007'}).status_code==200
    assert db.session.execute(text('SELECT pin_code FROM vendor_pins WHERE vendor_id=1')).scalar()=='0007'
    assert db.session.execute(text('SELECT count(*) FROM vendor_pins WHERE vendor_id=1')).scalar()==1

def test_password_same_value_rejected_and_response_private(security):
    response=change(security,{'kind':'password','current_password':'OldPassword123','new_value':'OldPassword123','confirm_value':'OldPassword123'})
    assert response.status_code==400
    assert response.headers['Cache-Control']=='private, no-store'

def test_other_cafe_pin_collision_is_readable(security):
    db.session.execute(text("INSERT INTO vendor_pins(vendor_id,pin_code) VALUES(2,'9274')"));db.session.commit()
    response=change(security,{'kind':'pin','current_password':'OldPassword123','new_value':'9274','confirm_value':'9274'})
    assert response.status_code==409 and 'PIN' in response.json['error']


def test_account_password_synchronizes_linked_cafes_only(security):
    from app.models.vendor import Vendor
    from app.models.vendorAccount import VendorAccount
    VendorAccount.__table__.create(db.engine,checkfirst=True)
    db.session.add(VendorAccount(id=1,email='owner@example.invalid',name='Owner'))
    db.session.flush()
    db.session.get(Vendor,1).account_id=1
    db.session.add_all([Vendor(id=2,cafe_name='Linked cafe',owner_name='Owner',timing_id=1,account_id=1),Vendor(id=3,cafe_name='Other cafe',owner_name='Other',timing_id=1)])
    db.session.execute(text("INSERT INTO password_manager VALUES(2,2,'vendor','DifferentLegacyPassword',false),(3,3,'vendor','OtherPassword123',false)"));db.session.commit()
    response=change(security,{'kind':'password','current_password':'OldPassword123','new_value':'NewPassword123','confirm_value':'NewPassword123'})
    assert response.status_code==200
    assert db.session.execute(text('SELECT password FROM password_manager ORDER BY id')).scalars().all()==['NewPassword123','NewPassword123','OtherPassword123']

def test_updated_owner_pin_is_used_by_real_kiosk_validation(security):
    if db.engine.dialect.name!='postgresql':pytest.skip('Persistent kiosk limiter requires PostgreSQL')
    from app.models.console import Console
    from app.models.console_link_session import ConsoleLinkSession
    from app.controllers.kiosk_controller import bp_kiosk,install_kiosk_errors
    security.register_blueprint(bp_kiosk);install_kiosk_errors(security)
    db.session.execute(text('CREATE TABLE kiosk_rate_limits(key text PRIMARY KEY,window_start timestamptz,attempts integer)'))
    db.session.add(Console(id=1,vendor_id=1,console_number=1,model_number='Test PC',serial_number='owner-test',brand='Test',console_type='pc'))
    db.session.flush()
    db.session.add(ConsoleLinkSession(id=1,vendor_id=1,console_id=1,kiosk_id='test-pc',session_token='local-owner-test-link',status='active'))
    db.session.execute(text("INSERT INTO vendor_pins(vendor_id,pin_code) VALUES(1,'4837')"));db.session.commit()
    assert change(security,{'kind':'pin','current_password':'OldPassword123','new_value':'0007','confirm_value':'0007'}).status_code==200
    client=security.test_client();headers={'Authorization':'Bearer local-owner-test-link'}
    old=client.post('/api/kiosk/owner-pin/validate',json={'pin':'4837','action':'force_exit'},headers=headers)
    new=client.post('/api/kiosk/owner-pin/validate',json={'pin':'0007','action':'force_exit'},headers=headers)
    assert old.status_code==401 and new.status_code==200 and new.json['authorized'] is True


def test_updated_password_matches_login_verifier(security):
    import ast
    from pathlib import Path
    from werkzeug.security import check_password_hash
    path=Path(__file__).parents[2]/'hfg-login-service/routes/auth_routes.py'
    tree=ast.parse(path.read_text());fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_verify_password')
    scope={'check_password_hash':check_password_hash}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),scope)
    response=change(security,{'kind':'password','current_password':'OldPassword123','new_value':'NewPassword123','confirm_value':'NewPassword123'})
    assert response.status_code==200
    stored=db.session.execute(text('SELECT password FROM password_manager WHERE parent_id=1')).scalar()
    assert scope['_verify_password'](stored,'NewPassword123')
    assert not scope['_verify_password'](stored,'OldPassword123')


def test_cross_cafe_owner_claim_cannot_change_credentials(security):
    token=create_access_token(identity='owner-1',additional_claims={'scope':'vendor_access','vendor_id':2,'staff':{'id':'owner-1','role':'owner','name':'Owner'}})
    response=security.test_client().post('/api/vendor/1/access/owner/security',json={'kind':'password','current_password':'OldPassword123','new_value':'NewPassword123','confirm_value':'NewPassword123'},headers={'Authorization':'Bearer '+token})
    assert response.status_code==403
    assert db.session.execute(text('SELECT password FROM password_manager WHERE parent_id=1')).scalar()=='OldPassword123'
