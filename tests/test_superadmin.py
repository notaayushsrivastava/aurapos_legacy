import unittest
import json
from unittest.mock import patch
from app import app, ADMIN_USER, ADMIN_PASSWORD, adminRepo

class TestSuperAdmin(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        try:
            adminRepo.set_setting("platform_maintenance", json.dumps({"active": False, "message": ""}))
        except Exception:
            pass

    def tearDown(self):
        try:
            adminRepo.set_setting("platform_maintenance", json.dumps({"active": False, "message": ""}))
        except Exception:
            pass

    def set_admin_session(self):
        with self.client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_user'] = ADMIN_USER

    def test_unauthenticated_admin_shows_login(self):
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Sign in to Admin", res.data)

    def test_admin_dashboard_renders(self):
        self.set_admin_session()
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"SuperAdmin Control Center", res.data)
        self.assertIn(b"Salons Directory", res.data)
        self.assertIn(b"Platform Analytics & GMV", res.data)

    def test_admin_health_api(self):
        self.set_admin_session()
        res = self.client.get('/admin/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('status'), 'healthy')
        self.assertIn('table_counts', data)
        self.assertIn('latency_ms', data)

    def test_admin_export_csv(self):
        self.set_admin_session()
        res = self.client.get('/admin/export-csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        self.assertIn(b"Salon Name", res.data)

    def test_admin_announcement_broadcast(self):
        self.set_admin_session()
        res = self.client.post('/admin/announcement', json={
            'message': 'Test broadcast announcement',
            'type': 'info',
            'active': True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data['announcement']['message'], 'Test broadcast announcement')

    def test_admin_maintenance_toggle(self):
        self.set_admin_session()
        res = self.client.post('/admin/maintenance-toggle', json={
            'active': False,
            'message': 'Maintenance mode disabled.'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertFalse(data['maintenance']['active'])

    def test_admin_salon_details_and_export(self):
        self.set_admin_session()
        res = self.client.get('/admin/api/salon/1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('salon', data)

        res_export = self.client.get('/admin/api/salon/1/export')
        self.assertEqual(res_export.status_code, 200)
        self.assertEqual(res_export.mimetype, 'application/json')

    def test_admin_impersonate_and_exit(self):
        self.set_admin_session()
        res = self.client.post('/admin/impersonate/1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('redirect_url'), '/dashboard')

        res_exit = self.client.get('/admin/exit-impersonation', follow_redirects=False)
        self.assertEqual(res_exit.status_code, 302)
        self.assertEqual(res_exit.headers.get('Location'), '/admin/')

    def test_admin_grant_plan_with_validity(self):
        self.set_admin_session()
        res = self.client.post('/admin/grant-plan', json={
            'salon_id': 1,
            'plan': 'pro',
            'cycle': 'monthly',
            'days': 30
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

    def test_admin_public_toggle(self):
        self.set_admin_session()
        res = self.client.post('/admin/public-toggle')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('accepting_public', data)

    @patch.object(adminRepo, "add_audit_log")
    @patch.object(adminRepo, "set_setting")
    @patch.object(adminRepo, "get_setting")
    def test_platform_status_and_maintenance_lockdown(self, mock_get_setting, mock_set_setting, mock_audit_log):
        self.set_admin_session()
        state = {"active": False, "message": ""}

        def fake_get_setting(key, default=None):
            if key == "platform_maintenance":
                return json.dumps(state)
            return default

        def fake_set_setting(key, value):
            if key == "platform_maintenance":
                state.clear()
                state.update(json.loads(value))
            return True

        mock_get_setting.side_effect = fake_get_setting
        mock_set_setting.side_effect = fake_set_setting

        res_maint = self.client.post('/admin/maintenance-toggle', json={
            'active': True,
            'message': 'Scheduled database upgrades in progress.'
        })
        self.assertEqual(res_maint.status_code, 200)

        res_status = self.client.get('/api/platform-status')
        self.assertEqual(res_status.status_code, 200)
        self.assertTrue(res_status.get_json()['maintenance']['active'])

        reg_client = app.test_client()
        res_reg = reg_client.get('/dashboard')
        self.assertEqual(res_reg.status_code, 503)
        self.assertIn(b"System Under Maintenance", res_reg.data)

        res_reg_api = reg_client.get('/api/bills')
        self.assertEqual(res_reg_api.status_code, 503)
        self.assertTrue(res_reg_api.get_json().get('maintenance'))

        res_admin = self.client.get('/admin/')
        self.assertEqual(res_admin.status_code, 200)

        res_off = self.client.post('/admin/maintenance-toggle', json={'active': False, 'message': ''})
        self.assertEqual(res_off.status_code, 200)

        res_restored = reg_client.get('/api/platform-status')
        self.assertEqual(res_restored.status_code, 200)
        self.assertFalse(res_restored.get_json()['maintenance']['active'])

if __name__ == '__main__':
    unittest.main()
