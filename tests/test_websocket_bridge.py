"""Run bridge functions with fake I/O so regressions cannot contact services."""
import ast
from pathlib import Path
import threading
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'app/services/websocket_service.py'
TREE = ast.parse(SOURCE.read_text())


def load(*names, **scope):
    functions = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    code = compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(SOURCE), 'exec')
    exec(code, scope)
    return scope


class StopLoop(BaseException):
    pass


class BridgeTests(unittest.TestCase):
    def test_admin_join_and_connect_return_without_waiting_for_disconnect(self):
        socket = Mock()
        socket.wait.side_effect = AssertionError('receive-loop wait blocks callback')
        scope = load('_join_upstream_admin', '_connect_upstream', _upstream_sio=socket,
                     _ns=lambda: None, _log_info=Mock(), _log_err=Mock(),
                     BOOKING_AUTH_TOKEN='', BOOKING_SOCKET_URL='http://test.invalid')
        scope['_join_upstream_admin']()
        scope['_connect_upstream']()
        socket.emit.assert_called_once_with('connect_admin', {})
        socket.connect.assert_called_once()
        socket.wait.assert_not_called()

    def test_health_supervisor_keeps_pinging(self):
        socket = Mock(connected=True)
        sleeps = []
        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 3:
                raise StopLoop()
        scope = load('_health_check_loop', _upstream_sio=socket,
                     time=SimpleNamespace(time=lambda: 100, sleep=sleep),
                     _last_admin_heartbeat=100, _last_pong=75,
                     _HEALTH_INTERVAL=20, _UPSTREAM_PING_TIMEOUT=20,
                     _REJOIN_QUIET_SECS=60, _RECONNECT_BACKOFF=30, _last_forced_reconnect=0,
                     _ns=lambda: None, _on_ping_ack=Mock(), _log_info=Mock(),
                     _log_warn=Mock(), _log_err=Mock())
        with self.assertRaises(StopLoop):
            scope['_health_check_loop']()
        self.assertEqual(socket.emit.call_count, 3)
        socket.disconnect.assert_not_called()  # one late heartbeat must not flap
        socket.wait.assert_not_called()

    def test_start_is_idempotent_with_one_connection_supervisor(self):
        thread = Mock()
        scope = load('start_upstream_bridge', _started_upstream=False,
                     _lock=threading.Lock(), _register_upstream_handlers=Mock(),
                     threading=SimpleNamespace(Thread=thread), _health_check_loop=Mock())
        scope['start_upstream_bridge'](None)
        scope['start_upstream_bridge'](None)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_cache_invalidates_before_emit_but_failure_does_not_drop_event(self):
        from typing import Optional, Dict, Any
        calls = []
        routes = ModuleType('app.routes')
        routes._invalidate_vendor_caches = Mock(side_effect=lambda vendor: calls.append('invalidate'))
        socket = SimpleNamespace(emit=lambda *a, **kw: calls.append('emit'))
        scope = load('_emit_downstream_to_vendor', Optional=Optional, Dict=Dict, Any=Any,
                     socketio=socket, _log_info=Mock(), _log_err=Mock())
        with patch.dict('sys.modules', {'app.routes': routes}):
            scope['_emit_downstream_to_vendor'](7, 'booking', {})
            self.assertEqual(calls, ['invalidate', 'emit'])
            routes._invalidate_vendor_caches.side_effect = RuntimeError('cache unavailable')
            scope['_emit_downstream_to_vendor'](7, 'booking', {})
            self.assertEqual(calls[-1], 'emit')
            self.assertEqual(calls.count('emit'), 2)


    def test_duplicate_upstream_booking_is_relayed_once(self):
        emitted = []
        lock = threading.Lock()
        clock = SimpleNamespace(t=1000.0)
        from typing import Dict, Any
        scope = load('_seen_recently', '_handle_upstream_booking', Dict=Dict, Any=Any,
                     _lock=lock, _recent_upstream={}, _DEDUPE_WINDOW_SECS=5.0,
                     time=SimpleNamespace(time=lambda: clock.t), _mark_pong=Mock(),
                     _emit_downstream_to_vendor=lambda vid, ev, data: emitted.append(ev),
                     format_upcoming_booking_from_upstream=lambda data: None,
                     _log_info=Mock(), _log_warn=Mock(), _log_err=Mock())
        vendor_copy = {'vendorId': 7, 'bookingId': 9, 'status': 'confirmed', 'booking_status': 'upcoming'}
        admin_copy = {'vendor_id': 7, 'booking_id': 9, 'status': 'confirmed', 'booking_status': 'upcoming'}
        scope['_handle_upstream_booking'](vendor_copy)
        scope['_handle_upstream_booking'](admin_copy)
        self.assertEqual(emitted, ['booking', 'booking_updated', 'booking_slots_updated'])
        scope['_handle_upstream_booking'](dict(vendor_copy, status='cancelled'))
        self.assertEqual(len(emitted), 6)  # a real status change still goes out
        clock.t += 6
        scope['_handle_upstream_booking'](vendor_copy)
        self.assertEqual(len(emitted), 9)

    def test_upstream_current_slot_unlocks_the_kiosk(self):
        unlock = Mock()
        from typing import Dict, Any
        scope = load('_handle_upstream_current_slot', Dict=Dict, Any=Any, _mark_pong=Mock(),
                     _emit_downstream_to_vendor=Mock(), _unlock_started_booking=unlock,
                     _log_info=Mock(), _log_warn=Mock(), _log_err=Mock())
        scope['_handle_upstream_current_slot']({'vendorId': 7, 'bookingId': 9, 'console_id': 3})
        unlock.assert_called_once_with(7, 9, 3)

    def test_unlock_skips_bookings_that_are_not_running(self):
        work = []
        scope = load('_unlock_started_booking', _seen_recently=lambda key: False,
                     _run_in_app=lambda fn: work.append(fn), _log_err=Mock())
        scope['_unlock_started_booking'](None, 9, 3)
        scope['_unlock_started_booking'](7, 'x', 3)
        self.assertEqual(work, [])
        scope['_unlock_started_booking'](7, 9, 3)
        self.assertEqual(len(work), 1)

    def test_bridge_listens_for_every_vendor_event_booking_emits(self):
        socket = Mock()
        names = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name.startswith('_handle_upstream')]
        from typing import Dict, Any
        scope = load('_register_upstream_handlers', '_relay_upstream', _upstream_sio=socket, Dict=Dict, Any=Any,
                     _ns=lambda: None, _log_info=Mock(), _log_warn=Mock(), _mark_pong=Mock(),
                     _join_upstream_admin=Mock(), _join_upstream_vendor=Mock(), _lock=threading.Lock(),
                     _joined_vendor_ids=set(), BOOKING_SOCKET_URL='http://test.invalid',
                     **{name: Mock() for name in names})
        scope['_register_upstream_handlers']()
        events = {c.args[0] for c in socket.on.call_args_list}
        for event in ('booking', 'booking_admin', 'current_slot', 'console_availability',
                      'pay_at_cafe_accepted', 'pay_at_cafe_rejected', 'booking_payment_update',
                      'kiosk_session_extended', 'booking_updated', 'gamers_credit_updated'):
            self.assertIn(event, events)
        self.assertTrue(all(c.kwargs.get('namespace') == '/' for c in socket.on.call_args_list))

if __name__ == '__main__':
    unittest.main()
