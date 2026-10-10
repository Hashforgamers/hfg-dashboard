from test_kiosk_runtime import KioskTests,load,db,security,runtime
from sqlalchemy import text

class OwnerPinTests(KioskTests):
    def setUp(self):
        super().setUp()
        db.session.execute(text('ALTER TABLE vendors ADD COLUMN owner_name text'))
        db.session.execute(text("CREATE TABLE vendor_pins(vendor_id integer,pin_code text); INSERT INTO vendor_pins VALUES(1,'4837'),(2,'9274')"));db.session.commit()
        module=load('app/controllers/kiosk_controller.py',__name__=__name__,db=db,**{name:security[name] for name in ('KioskError','runtime_identity','positive_id','check_scope','rate_limit')},booking_window=runtime['booking_window'],expire_vendor=runtime['expire_vendor'],secure_start=runtime['secure_start'])
        self.app.register_blueprint(module['bp_kiosk'])
    def test_owner_exit_validates_link_and_returns_no_pin(self):
        result=self.post('/api/kiosk/owner-pin/validate',{'pin':'4837','action':'force_exit'})
        self.assertEqual(result.status_code,200);self.assertTrue(result.json['authorized'])
        self.assertEqual(result.json['console_id'],10);self.assertEqual(result.json['owner']['role'],'owner')
        self.assertNotIn('4837',result.get_data(as_text=True))
        self.assertEqual(result.headers['Cache-Control'],'private, no-store')
        self.assertFalse(db.session.execute(text('SELECT is_available FROM vendor_1_console_availability WHERE console_id=10')).scalar())
    def test_wrong_cafe_pin_cannot_authorize_exit(self):
        self.assertEqual(self.post('/api/kiosk/owner-pin/validate',{'pin':'9274','action':'force_exit'}).status_code,401)
    def test_invalid_action_and_missing_token(self):
        self.assertEqual(self.post('/api/kiosk/owner-pin/validate',{'pin':'4837','action':'unlock'}).status_code,400)
        self.assertEqual(self.post('/api/kiosk/owner-pin/validate',{'pin':'4837','action':'force_exit'},token=None).status_code,401)
    def test_owner_pin_validation_rate_limited(self):
        for _ in range(10):self.assertEqual(self.post('/api/kiosk/owner-pin/validate',{'pin':'0000','action':'force_exit'}).status_code,401)
        self.assertEqual(self.post('/api/kiosk/owner-pin/validate',{'pin':'4837','action':'force_exit'}).status_code,429)

    def test_admin_settings_authorization_is_action_specific(self):
        result=self.post('/api/kiosk/owner-pin/validate',{'pin':'4837','action':'admin_settings'})
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json['authorized'])
        self.assertEqual(result.json['action'],'admin_settings')
        self.assertEqual(result.json['expires_in_seconds'],60)
        wrong=self.post('/api/kiosk/owner-pin/validate',{'pin':'9274','action':'admin_settings'})
        self.assertEqual(wrong.status_code,401)
