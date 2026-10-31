"""Exercise the production business-details handler against isolated SQL storage."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

ROOT=Path(__file__).resolve().parents[1]


def production_public_name(path):
    cls=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Vendor')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='public_name')
    method.decorator_list=[]
    scope={}
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),scope)
    return scope['public_name']


@pytest.fixture
def api():
    app=Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI']='sqlite://'
    db=SQLAlchemy(app)
    class Vendor(db.Model):
        id=db.Column(db.Integer,primary_key=True)
        cafe_name=db.Column(db.String(255),nullable=False)
        display_name=db.Column(db.String(120))
        public_name=property(production_public_name(ROOT/'app/models/vendor.py'))
        contact_info=website=physical_address=None
    route=next(n for n in ast.parse((ROOT/'app/routes.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='update_business_details')
    route.decorator_list=[]
    invalidations=[]
    scope=dict(db=db,Vendor=Vendor,request=request,jsonify=jsonify,SQLAlchemyError=SQLAlchemyError,current_app=app,
               _invalidate_vendor_caches=invalidations.append)
    exec(compile(ast.Module(body=[route],type_ignores=[]),'routes.py','exec'),scope)
    app.add_url_rule('/vendor/<int:vendor_id>/business-details',view_func=scope['update_business_details'],methods=['PATCH'])
    with app.app_context():
        db.create_all()
        db.session.add(Vendor(id=1,cafe_name='Registered Gaming Pvt Ltd'))
        db.session.commit()
        yield SimpleNamespace(client=app.test_client(),db=db,Vendor=Vendor,invalidations=invalidations)


def test_display_name_save_reload_clear_keeps_business_identity(api):
    response=api.client.patch('/vendor/1/business-details',json={'displayName':'  Neon   Arena  '})
    assert response.status_code==200,response.json
    assert response.json['data']['displayName']=='Neon Arena'
    assert response.json['data']['businessName']=='Registered Gaming Pvt Ltd'
    api.db.session.expire_all()
    vendor=api.db.session.get(api.Vendor,1)
    assert vendor.display_name=='Neon Arena' and vendor.public_name=='Neon Arena'
    assert api.invalidations==[1]
    response=api.client.patch('/vendor/1/business-details',json={'displayName':'   '})
    assert response.status_code==200
    assert response.json['data']['publicName']=='Registered Gaming Pvt Ltd'
    assert vendor.display_name is None


@pytest.mark.parametrize('value',[123,[],{},'x'*121,'bad\x00name'])
def test_invalid_display_name_does_not_change_business_or_public_name(api,value):
    response=api.client.patch('/vendor/1/business-details',json={'displayName':value})
    assert response.status_code==400,response.json
    api.db.session.expire_all()
    vendor=api.db.session.get(api.Vendor,1)
    assert vendor.display_name is None
    assert vendor.cafe_name=='Registered Gaming Pvt Ltd'
    assert not api.invalidations


def test_business_name_update_preserves_custom_public_name(api):
    assert api.client.patch('/vendor/1/business-details',json={'displayName':'Neon Arena'}).status_code==200
    response=api.client.patch('/vendor/1/business-details',json={'businessName':'New Legal Pvt Ltd'})
    assert response.json['data']['publicName']=='Neon Arena'
    assert response.json['data']['businessName']=='New Legal Pvt Ltd'


@pytest.mark.parametrize('model',['hfg-dashboard-service/app/models/vendor.py','hfg-onboard/models/vendor.py','hfg-booking/models/vendor.py','hfg-user-onboard/models/vendor.py'])
def test_all_public_name_consumers_have_the_same_fallback(model):
    name=production_public_name(ROOT.parent/model)
    assert name(SimpleNamespace(display_name=None,cafe_name='Legal Name'))=='Legal Name'
    assert name(SimpleNamespace(display_name='  Arena  ',cafe_name='Legal Name'))=='Arena'
