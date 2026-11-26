"""The marketplace buyer endpoint only vouches for the cafe the token belongs to."""
import sys
import time
import types
from types import SimpleNamespace

import jwt
import pytest
from flask import Flask

SECRET = "test-secret-that-is-long-enough-for-hs256"


@pytest.fixture
def api(monkeypatch):
    vendors = {
        7: SimpleNamespace(
            id=7, cafe_name="Pixel Den", display_name=None, owner_name="Asha",
            contact_info=SimpleNamespace(email="den@example.test", phone="9876543210"),
            physical_address=SimpleNamespace(addressLine1="12 MG Road, Bengaluru", addressLine2=None, pincode="560001", state="Karnataka", country="India"),
        )
    }
    fake_vendor_module = types.ModuleType("app.models.vendor")
    fake_vendor_module.Vendor = SimpleNamespace(query=SimpleNamespace(get=lambda vid: vendors.get(vid)))
    monkeypatch.setitem(sys.modules, "app.models.vendor", fake_vendor_module)
    sys.modules.pop("app.controllers.marketplace_buyer_controller", None)
    from app.controllers import marketplace_buyer_controller as module

    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = SECRET
    app.register_blueprint(module.bp_marketplace_buyer)
    return SimpleNamespace(client=app.test_client(), module=module)


def token(claims, exp_in=3600):
    return jwt.encode({**claims, "exp": int(time.time()) + exp_in}, SECRET, algorithm="HS256")


def get(api, vid, tok):
    return api.client.get(f"/api/vendor/{vid}/marketplace/buyer", headers={"Authorization": f"Bearer {tok}"} if tok else {})


def test_owner_login_token_returns_the_cafe_profile(api):
    res = get(api, 7, token({"sub": {"id": 7, "type": "vendor"}}))
    assert res.status_code == 200
    buyer = res.get_json()["buyer"]
    assert buyer["vendor_id"] == 7 and buyer["cafe_name"] == "Pixel Den"
    assert buyer["email"] == "den@example.test" and buyer["address"]["pincode"] == "560001"
    assert res.headers["Cache-Control"] == "private, no-store"


def test_rejects_missing_expired_forged_and_other_cafe_tokens(api):
    assert get(api, 7, None).status_code == 401
    assert get(api, 7, token({"sub": {"id": 7, "type": "vendor"}}, exp_in=-10)).status_code == 401
    forged = jwt.encode({"sub": {"id": 7, "type": "vendor"}, "exp": int(time.time()) + 60}, "wrong-secret-wrong-secret-wrong", algorithm="HS256")
    assert get(api, 7, forged).status_code == 401
    assert get(api, 7, token({"sub": {"id": 8, "type": "vendor"}})).status_code == 403
    assert get(api, 7, token({"sub": {"id": 7, "type": "user"}})).status_code == 403


def test_unknown_cafe_is_404(api):
    assert get(api, 9, token({"sub": {"id": 9, "type": "vendor"}})).status_code == 404


def test_staff_tokens_need_a_live_session_with_store_permission():
    from app.controllers.marketplace_buyer_controller import BuyerError, authorize_buyer
    staff = {"scope": "vendor_access", "vendor_id": 7, "jti": "j1", "staff": {"id": "3", "role": "staff"}}
    authorize_buyer(staff, 7, staff_allowed=lambda c, v: True)
    with pytest.raises(BuyerError) as denied:
        authorize_buyer(staff, 7, staff_allowed=lambda c, v: False)
    assert denied.value.status == 403
    with pytest.raises(BuyerError) as mismatch:
        authorize_buyer({**staff, "vendor_id": 8}, 7, staff_allowed=lambda c, v: True)
    assert mismatch.value.status == 403
