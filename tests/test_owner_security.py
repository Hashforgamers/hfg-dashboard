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
    monkeypatch.setattr(cafe_wallet_controller,'staff_actor',lambda vendor,permission:{'id':'owner-1','name':'Owner'})
    monkeypatch.setattr(cafe_wallet_service,'audit',Mock())
    db.session.execute(text('CREATE TABLE password_manager(id integer PRIMARY KEY,parent_id integer,parent_type text,password text,must_change_password boolean)'))
    db.session.execute(text('CREATE TABLE vendor_pins(id '+('serial' if db.engine.dialect.name=='postgresql' else 'integer')+' PRIMARY KEY,vendor_id integer,pin_code text UNIQUE)'))
    from app.models.vendorStaff import VendorStaff
    VendorStaff.__table__.create(db.engine,checkfirst=True)
    db.session.execute(text("INSERT INTO password_manager VALUES(1,1,'vendor','OldPassword123',false)"));db.session.commit()
    return commerce

def change(a,body,role='owner'):
    token=create_access_token(identity='owner-1',additional_claims={'scope':'vendor_access','vendor_id':1,'staff':{'id':'owner-1','role':role}})
    return a.test_client().post('/api/vendor/1/access/owner/security',json=body,headers={'Authorization':'Bearer '+token})

def test_owner_password_requires_current_password(security):
    body={'kind':'password','current_password':'wrong','new_value':'NewPassword123','confirm_value':'NewPassword123'}
    assert change(security,body).status_code==401
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
