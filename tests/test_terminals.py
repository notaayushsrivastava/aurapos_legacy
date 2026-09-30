import unittest
import json
import time
from app import app, terminalRepo, authRepo, adminRepo
from backend import get_terminal_limit, TIER_TERMINAL_LIMITS

class TestPOSMultiTerminals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = app.test_client()
        # Ensure maintenance mode is off for testing
        try:
            adminRepo.set_setting("platform_maintenance", json.dumps({"active": False, "message": ""}))
        except Exception:
            pass
        # Clean any terminal sessions & drafts for salon 1 before each test
        try:
            terminalRepo.release_session(1, "tab_test_1")
            terminalRepo.release_session(1, "tab_test_2")
            terminalRepo.release_session(1, "tab_test_3")
            terminalRepo.release_session(1, "tab_test_4")
            terminalRepo.release_session(1, "tab_test_5")
            terminalRepo.delete_draft(1, 1)
            terminalRepo.delete_draft(1, 2)
            terminalRepo.delete_draft(1, 3)
            terminalRepo.delete_draft(1, 4)
            terminalRepo.delete_draft(1, 5)
        except Exception:
            pass

    def tearDown(self):
        # Reset salon 1 plan back to free
        try:
            adminRepo.update_salon(1, {"plan": "free"})
            adminRepo.set_setting("platform_maintenance", json.dumps({"active": False, "message": ""}))
        except Exception:
            pass

    def set_salon_session(self, salon_id=1, username="test_staff"):
        with self.client.session_transaction() as sess:
            sess['id'] = salon_id
            sess['salon_name'] = "Test Salon"
            sess['account_id'] = 101
            sess['username'] = username

    def test_tier_limits_mapping(self):
        """Test the tier limits adhere strictly to specifications."""
        self.assertEqual(get_terminal_limit("free"), 1)
        self.assertEqual(get_terminal_limit("pro"), 3)
        self.assertIsNone(get_terminal_limit("studio"))
        # Fallback to free (1) for unknown tiers
        self.assertEqual(get_terminal_limit("unknown"), 1)

    def test_repository_heartbeat_and_lease(self):
        """Test repository direct lease creation, refresh, and release."""
        terminalRepo.clean_stale_sessions(timeout_seconds=0)

        # Tab 1 takes terminal 1
        res1 = terminalRepo.heartbeat(salon_id=999, terminal_id=1, tab_id="tab_A", plan="free")
        self.assertTrue(res1['allowed'])
        self.assertEqual(len(res1['active_terminals']), 1)

        # Same tab refreshing heartbeat succeeds
        res1_refresh = terminalRepo.heartbeat(salon_id=999, terminal_id=1, tab_id="tab_A", plan="free")
        self.assertTrue(res1_refresh['allowed'])

        # Tab 2 trying to open another terminal on a 1-terminal limit (free) is blocked
        res2 = terminalRepo.heartbeat(salon_id=999, terminal_id=2, tab_id="tab_B", plan="free")
        self.assertFalse(res2['allowed'])
        self.assertEqual(res2['reason'], 'limit_reached')

        # Release Tab 1
        rel = terminalRepo.release_session(salon_id=999, tab_id="tab_A")
        self.assertTrue(rel)

        # Tab 2 can now claim terminal 2
        res2_retry = terminalRepo.heartbeat(salon_id=999, terminal_id=2, tab_id="tab_B", plan="free")
        self.assertTrue(res2_retry['allowed'])

        # Clean up
        terminalRepo.release_session(salon_id=999, tab_id="tab_B")

    def test_repository_takeover(self):
        """Test takeover logic when a user takes over a terminal in another tab."""
        terminalRepo.heartbeat(salon_id=998, terminal_id=1, tab_id="tab_old", plan="free")
        
        # New tab takes over terminal 1
        takeover_res = terminalRepo.takeover_terminal(salon_id=998, terminal_id=1, tab_id="tab_new", plan="free")
        self.assertTrue(takeover_res['allowed'])

        # Now tab_new is allowed and holds the terminal
        active = terminalRepo.get_active_sessions(salon_id=998)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['tab_id'], "tab_new")

        # Clean up
        terminalRepo.release_session(salon_id=998, tab_id="tab_new")

    def test_repository_draft_storage(self):
        """Test server-side draft persistence for Studio tier."""
        cart_payload = {
            "items": [{"name": "Haircut Deluxe", "price": 450, "qty": 1, "type": "service"}],
            "client_name": "Alice Wonderland",
            "client_phone": "9876543210",
            "discount": 10
        }

        # Save draft
        saved = terminalRepo.save_draft(salon_id=997, terminal_id=1, terminal_name="Terminal #01",
                                       cart_data=cart_payload, account_id=42, account_name="staff1")
        self.assertTrue(saved)

        # Retrieve draft
        draft = terminalRepo.get_draft(salon_id=997, terminal_id=1)
        self.assertIsNotNone(draft)
        self.assertEqual(draft['terminal_name'], "Terminal #01")
        self.assertEqual(draft['cart_data']['client_name'], "Alice Wonderland")
        self.assertEqual(len(draft['cart_data']['items']), 1)
        self.assertEqual(draft['cart_data']['discount'], 10)

        # Retrieve all drafts
        drafts = terminalRepo.get_drafts(salon_id=997)
        self.assertTrue(any(d['terminal_id'] == 1 for d in drafts))

        # Delete draft
        deleted = terminalRepo.delete_draft(salon_id=997, terminal_id=1)
        self.assertTrue(deleted)
        self.assertIsNone(terminalRepo.get_draft(salon_id=997, terminal_id=1))

    def test_free_tier_enforces_single_terminal(self):
        """Free tier allows only 1 terminal session at a time; 2nd tab is blocked."""
        adminRepo.update_salon(1, {"plan": "free"})
        self.set_salon_session(salon_id=1)

        # Tab 1 heartbeat for Terminal #1
        r1 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1,
            'tab_id': 'tab_test_1',
            'terminal_name': 'Terminal #01'
        })
        self.assertEqual(r1.status_code, 200)
        d1 = r1.get_json()
        self.assertTrue(d1['allowed'])
        self.assertEqual(d1['limit'], 1)

        # Tab 2 heartbeat (different browser tab opening /billing) is rejected
        r2 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 2,
            'tab_id': 'tab_test_2',
            'terminal_name': 'Terminal #02'
        })
        self.assertEqual(r2.status_code, 200)
        d2 = r2.get_json()
        self.assertFalse(d2['allowed'])
        self.assertEqual(d2['reason'], 'limit_reached')
        self.assertIn("limit reached", d2['message'])

    def test_free_and_pro_tier_drafts_blocked_from_server(self):
        """Free and Pro tiers cannot save drafts server-side (Pro is cookie-only)."""
        adminRepo.update_salon(1, {"plan": "free"})
        self.set_salon_session(salon_id=1)

        # Free tier GET /api/terminals/drafts -> returns cloud_sync=False, drafts=[]
        r_free_get = self.client.get('/api/terminals/drafts')
        self.assertEqual(r_free_get.status_code, 200)
        self.assertFalse(r_free_get.get_json()['cloud_sync'])
        self.assertEqual(r_free_get.get_json()['drafts'], [])

        # Change to Pro
        adminRepo.update_salon(1, {"plan": "pro"})

        # Pro tier GET /api/terminals/drafts -> returns cloud_sync=False, drafts=[]
        r_pro_get = self.client.get('/api/terminals/drafts')
        self.assertEqual(r_pro_get.status_code, 200)
        self.assertFalse(r_pro_get.get_json()['cloud_sync'])
        self.assertEqual(r_pro_get.get_json()['drafts'], [])

        # Pro tier POST /api/terminals/drafts -> 403 Forbidden (browser cookie caching only)
        r_pro_post = self.client.post('/api/terminals/drafts', json={
            'terminal_id': 1,
            'cart_data': {}
        })
        self.assertEqual(r_pro_post.status_code, 403)
        self.assertFalse(r_pro_post.get_json()['success'])
        self.assertIn("Studio plan", r_pro_post.get_json()['message'])

    def test_pro_tier_allows_up_to_3_terminals(self):
        """Pro tier allows up to 3 parallel terminals; 4th terminal is blocked."""
        adminRepo.update_salon(1, {"plan": "pro"})
        self.set_salon_session(salon_id=1)

        # Open Terminal 1
        r1 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_1', 'terminal_name': 'Terminal #01'
        })
        self.assertTrue(r1.get_json()['allowed'])

        # Open Terminal 2
        r2 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 2, 'tab_id': 'tab_test_2', 'terminal_name': 'Terminal #02'
        })
        self.assertTrue(r2.get_json()['allowed'])

        # Open Terminal 3
        r3 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 3, 'tab_id': 'tab_test_3', 'terminal_name': 'Terminal #03'
        })
        self.assertTrue(r3.get_json()['allowed'])

        # Open 4th Terminal -> Blocked
        r4 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 4, 'tab_id': 'tab_test_4', 'terminal_name': 'Terminal #04'
        })
        self.assertFalse(r4.get_json()['allowed'])
        self.assertEqual(r4.get_json()['reason'], 'limit_reached')
        self.assertEqual(r4.get_json()['limit'], 3)

    def test_multi_tab_cannot_exceed_3_terminals_on_pro(self):
        """Ensure opening multiple tabs cannot bypass the 3-terminal Pro limit."""
        adminRepo.update_salon(1, {"plan": "pro"})
        self.set_salon_session(salon_id=1)

        # Tab 1 opens with Terminal 1 & 2
        r1 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_1', 'open_terminal_ids': [1, 2]
        })
        self.assertTrue(r1.get_json()['allowed'])
        self.assertEqual(sorted(r1.get_json()['open_terminals']), [1, 2])

        # Tab 2 opens with Terminal 3
        r2 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 3, 'tab_id': 'tab_test_2', 'open_terminal_ids': [3]
        })
        self.assertTrue(r2.get_json()['allowed'])

        # Now all 3 terminals (1, 2, 3) are active across Tab 1 and Tab 2.
        # Tab 3 opens in the browser and tries to open any terminal:
        # Requesting terminal 1 -> blocked (in_use)
        r3_t1 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_3', 'open_terminal_ids': [1]
        })
        self.assertFalse(r3_t1.get_json()['allowed'])
        self.assertEqual(r3_t1.get_json()['reason'], 'in_use')

        # Requesting terminal 3 -> blocked (in_use)
        r3_t3 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 3, 'tab_id': 'tab_test_3', 'open_terminal_ids': [3]
        })
        self.assertFalse(r3_t3.get_json()['allowed'])
        self.assertEqual(r3_t3.get_json()['reason'], 'in_use')

        # Requesting terminal 4 -> blocked (limit_reached: max 3)
        r3_t4 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 4, 'tab_id': 'tab_test_3', 'open_terminal_ids': [4]
        })
        self.assertFalse(r3_t4.get_json()['allowed'])
        self.assertEqual(r3_t4.get_json()['reason'], 'limit_reached')

        # Tab 2 releases terminal 3
        self.client.post('/api/terminals/release', json={
            'tab_id': 'tab_test_2', 'terminal_id': 3
        })

        # Now Tab 3 CAN claim terminal 3
        r3_retry = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 3, 'tab_id': 'tab_test_3', 'open_terminal_ids': [3]
        })
        self.assertTrue(r3_retry.get_json()['allowed'])

    def test_tab_holding_3_terminals_blocks_new_tab(self):
        """When 1 tab has 3 sub-terminals open, a new tab cannot open any terminal."""
        adminRepo.update_salon(1, {"plan": "pro"})
        self.set_salon_session(salon_id=1)

        # Tab 1 opens all 3 terminals
        r1 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_1', 'open_terminal_ids': [1, 2, 3]
        })
        self.assertTrue(r1.get_json()['allowed'])
        self.assertEqual(sorted(r1.get_json()['open_terminals']), [1, 2, 3])

        # Tab 2 opens and tries to heartbeat
        r2 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 2, 'tab_id': 'tab_test_2', 'open_terminal_ids': [2]
        })
        self.assertFalse(r2.get_json()['allowed'])
        self.assertEqual(r2.get_json()['reason'], 'in_use')

        # Tab 2 tries terminal 4
        r2_t4 = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 4, 'tab_id': 'tab_test_2', 'open_terminal_ids': [4]
        })
        self.assertFalse(r2_t4.get_json()['allowed'])
        self.assertEqual(r2_t4.get_json()['reason'], 'limit_reached')

    def test_studio_tier_unlimited_terminals_and_server_drafts(self):
        """Studio tier allows unlimited terminals and supports server-side draft sync."""
        adminRepo.update_salon(1, {"plan": "studio"})
        self.set_salon_session(salon_id=1, username="alex")

        # Open 4 terminals in parallel
        for i in range(1, 5):
            res = self.client.post('/api/terminals/heartbeat', json={
                'terminal_id': i, 'tab_id': f'tab_test_{i}', 'terminal_name': f'Terminal #0{i}'
            })
            self.assertTrue(res.get_json()['allowed'])
            self.assertIsNone(res.get_json()['limit'])

        # Save draft on Terminal 2 from user "alex"
        draft_payload = {
            'terminal_id': 2,
            'terminal_name': 'Terminal #02 (VIP Chair)',
            'cart_data': {
                'items': [{'name': 'Balayage Color', 'price': 2200, 'qty': 1}],
                'client_name': 'Sophia Loren',
                'client_phone': '9988776655',
                'discount': 15,
                'notes': 'Patch test cleared'
            }
        }
        res_save = self.client.post('/api/terminals/drafts', json=draft_payload)
        self.assertEqual(res_save.status_code, 200)
        self.assertTrue(res_save.get_json()['success'])

        # Another staff member / device signs into the same salon
        self.set_salon_session(salon_id=1, username="sarah_receptionist")

        # Fetches drafts -> can see and continue Terminal 2 draft!
        res_get = self.client.get('/api/terminals/drafts')
        self.assertEqual(res_get.status_code, 200)
        drafts = res_get.get_json().get('drafts', [])
        t2_draft = next((d for d in drafts if d['terminal_id'] == 2), None)
        self.assertIsNotNone(t2_draft)
        self.assertEqual(t2_draft['terminal_name'], 'Terminal #02 (VIP Chair)')
        self.assertEqual(t2_draft['cart_data']['client_name'], 'Sophia Loren')
        self.assertEqual(t2_draft['cart_data']['discount'], 15)

        # Delete draft
        res_del = self.client.delete('/api/terminals/drafts/2')
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()['success'])

        # Verify it's cleared
        res_get2 = self.client.get('/api/terminals/drafts')
        drafts_after = res_get2.get_json().get('drafts', [])
        self.assertFalse(any(d['terminal_id'] == 2 for d in drafts_after))

    def test_takeover_endpoint(self):
        """Test the POST /api/terminals/takeover endpoint."""
        adminRepo.update_salon(1, {"plan": "free"})
        self.set_salon_session(salon_id=1)

        # Tab 1 has terminal 1
        self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_1', 'terminal_name': 'Terminal #01'
        })

        # Tab 2 calls takeover
        res_takeover = self.client.post('/api/terminals/takeover', json={
            'terminal_id': 1, 'tab_id': 'tab_test_2', 'terminal_name': 'Terminal #01'
        })
        self.assertEqual(res_takeover.status_code, 200)
        data = res_takeover.get_json()
        self.assertTrue(data['allowed'])
        self.assertEqual(data['terminal_id'], 1)

        # Now tab_test_2 can heartbeat without being blocked
        res_hb = self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_2', 'terminal_name': 'Terminal #01'
        })
        self.assertTrue(res_hb.get_json()['allowed'])

    def test_non_billing_pages_not_restricted(self):
        """Ensure other pages (/dashboard, /appointments, /reports) are NOT blocked across tabs."""
        adminRepo.update_salon(1, {"plan": "free"})
        self.set_salon_session(salon_id=1)

        # Tab 1 has billing terminal open
        self.client.post('/api/terminals/heartbeat', json={
            'terminal_id': 1, 'tab_id': 'tab_test_1', 'terminal_name': 'Terminal #01'
        })

        # Other pages load normally (HTTP 200)
        r_dash = self.client.get('/dashboard')
        self.assertEqual(r_dash.status_code, 200)

        r_appts = self.client.get('/appointments')
        self.assertEqual(r_appts.status_code, 200)

        r_reports = self.client.get('/reports')
        self.assertEqual(r_reports.status_code, 200)


if __name__ == '__main__':
    unittest.main()
