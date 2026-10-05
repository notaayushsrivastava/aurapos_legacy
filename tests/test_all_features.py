import unittest
import json
import io
from datetime import datetime
from uuid import uuid4
from app import app, authRepo, billRepo, staffRepo

class TestAllFeatures(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_static_seo_and_robots(self):
        # Test robots.txt
        res = self.client.get('/robots.txt')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"User-agent: *", res.data)
        self.assertIn(b"Disallow: /admin", res.data)
        self.assertTrue(b"aurapos.aayushsrivastava.com" in res.data or b"aurapos3.vercel.app" in res.data)

        # Test llms.txt
        res = self.client.get('/llms.txt')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"AuraPOS", res.data)
        self.assertIn(b"Kinetic", res.data)

        # Test og-share-logo.png
        res = self.client.get('/assets/og-share-logo.png')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content_type.startswith('image/png'))

        # Test sitemap.xml
        res = self.client.get('/sitemap.xml')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content_type.startswith('application/xml'))
        self.assertIn(b"<urlset", res.data)
        self.assertIn(b"<loc>", res.data)
        self.assertIn(b"/pricing", res.data)
        self.assertIn(b"/booking", res.data)
        self.assertIn(b"/register", res.data)

        # Test sitemap redirect
        res = self.client.get('/sitemap')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get('Location'), '/sitemap.xml')

    def test_booking_showcase_and_vanity(self):
        # /booking should showcase demo booking portal
        res = self.client.get('/booking')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b"booking-preview" in res.data)
        self.assertIn(b"Turn Browsers Into", res.data)

        # /b/<slug> for a salon
        salon = authRepo.get_salon(1)
        if not salon:
            authRepo.create_auth("Test Owner", "9999999999", "admin", "Admin123!", "Test Salon", "test@aurasalon.com")
            salon = authRepo.get_salon(1)
        self.assertIsNotNone(salon)
        self.assertIsNotNone(salon.booking_slug)
        self.assertEqual(len(salon.booking_slug), 5)

        res = self.client.get(f'/b/{salon.booking_slug}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(salon.salon_name.encode(), res.data)

    def test_payment_settings_api(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # GET payment settings
        res = self.client.get('/api/settings/payment-methods')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('methods', data)

        # POST payment settings update
        res = self.client.post('/api/settings/payment-methods', json={'methods': {'upi': 'salon@upi', 'card_terminal': 'EDC-123'}})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_billing_with_split_payments(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # Create bill with split payment
        split_payload = {
            'client_name': 'Siddharth Roy',
            'client_phone': '9876543210',
            'subtotal': 2000,
            'discount': 200,
            'tax': 324,
            'grand_total': 2124,
            'payment_mode': 'Split (UPI: ₹1000, Cash: ₹1124)',
            'splits': [
                {'method': 'UPI', 'amount': 1000},
                {'method': 'Cash', 'amount': 1124}
            ],
            'items': [
                {'name': "Executive Men's Haircut", 'price': 400, 'qty': 1, 'staff': 'Alex'},
                {'name': "Hydra-Dew Glow Facial", 'price': 1600, 'qty': 1, 'staff': 'Sarah'}
            ]
        }
        res = self.client.post('/api/bills', json=split_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('bill_id', data)

    def test_pages_render_without_errors(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # Billing page
        res = self.client.get('/billing')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"printable-receipt", res.data)
        self.assertIn(b"Collect Payment", res.data)
        self.assertIn(b"Split Payment", res.data)

        # Settings page
        res = self.client.get('/settings')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Salon Profile", res.data)
        self.assertIn(b"Team Accounts", res.data)
        self.assertIn(b"Booking Link", res.data)

    def test_pricing_links_and_learn_more_tiers(self):
        # /pricing and /prices routes
        res = self.client.get('/pricing')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get('Location'), '/#pricing')

        res = self.client.get('/prices')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get('Location'), '/#pricing')

        # Landing page contains pricing anchors and Learn More
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="pricing"', res.data)
        self.assertIn(b'id="ch-pricing"', res.data)
        self.assertIn(b'id="prices"', res.data)
        self.assertIn(b'id="features"', res.data)
        self.assertIn(b'Detailed Difference Between Free, Pro &amp; Studio Tiers', res.data)
        self.assertIn(b'Free vs Pro vs Studio: Which Tier Fits Your Salon?', res.data)

        # Register page contains Learn More comparison
        res = self.client.get('/register')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'register-tiers-comparison', res.data)
        self.assertIn(b'Difference between Free, Pro &amp; Studio Tiers', res.data)
        self.assertIn(b'Tier &amp; Feature Comparison', res.data)

    def test_customers_directory_rbac_and_api(self):
        # 1. Unauthenticated redirect
        res = self.client.get('/customers')
        self.assertEqual(res.status_code, 302)

        # 2. Cashier role forbidden / redirected to /billing
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'cashier_user'
            sess['auth_level'] = 'cashier'

        res = self.client.get('/customers')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get('Location'), '/billing')

        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 403)

        # 3. Admin / Manager role allowed
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        res = self.client.get('/customers')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Customer Directory", res.data)
        self.assertIn(b"Mass Upload", res.data)

        # 4. API endpoints
        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

    def test_custom_payment_methods_and_billing(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. Update payment methods with custom options like Cheque, Demand Draft
        payload = {
            "methods": {
                "upi": "salon@okaxis",
                "card_terminal": "PineLabs Pro",
                "custom_methods": ["Cheque", "Demand Draft (DD)", "Bank Transfer"]
            }
        }
        res = self.client.put('/api/settings/payment-methods', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['methods']['custom_methods'], ["Cheque", "Demand Draft (DD)", "Bank Transfer"])

        # 2. Get payment methods
        res = self.client.get('/api/settings/payment-methods')
        self.assertEqual(res.status_code, 200)
        get_data = res.get_json()
        self.assertTrue(get_data['success'])
        self.assertEqual(get_data['methods']['custom_methods'], ["Cheque", "Demand Draft (DD)", "Bank Transfer"])

        # 3. Create a bill with custom payment method (e.g. Cheque)
        bill_payload = {
            "terminal_id": "POS-01",
            "client_name": "Test Patron",
            "client_phone": "9988776655",
            "subtotal": 1200,
            "discount": 0,
            "tax": 0,
            "grand_total": 1200,
            "payment_mode": "Cheque (CHQ #889900)",
            "items": [{"name": "Deluxe Haircut", "price": 1200, "qty": 1, "staff": "Unassigned"}]
        }
        b_res = self.client.post('/api/bills', json=bill_payload)
        self.assertEqual(b_res.status_code, 200)
        b_data = b_res.get_json()
        self.assertTrue(b_data['success'])
    def test_dynamic_rbac_system(self):
        # 1. Fetch system permissions
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        res = self.client.get('/api/settings/permissions')
        self.assertEqual(res.status_code, 200)
        p_data = res.get_json()
        self.assertTrue(p_data['success'])
        self.assertTrue(len(p_data['permissions']) >= 20)
        self.assertIn("Point of Sale", p_data['grouped'])

        # 2. Fetch default roles
        res = self.client.get('/api/settings/roles')
        self.assertEqual(res.status_code, 200)
        r_data = res.get_json()
        self.assertTrue(r_data['success'])
        roles = r_data['roles']
        role_names = [r['role_name'] for r in roles]
        self.assertIn("Owner", role_names)
        self.assertIn("Manager", role_names)
        self.assertIn("Billing Desk", role_names)

        # 3. Create a custom role
        custom_role_payload = {
            "role_name": "Weekend Shift Lead",
            "description": "Can process POS bills and manage appointments, but cannot edit inventory or view financial reports",
            "permissions": ["billing:read", "billing:write", "billing:discount", "appointments:read", "appointments:write"]
        }
        res = self.client.post('/api/settings/roles', json=custom_role_payload)
        self.assertEqual(res.status_code, 200)
        c_data = res.get_json()
        self.assertTrue(c_data['success'])
        created_role_id = c_data['role_id']

        # Verify duplicate creation rejection
        dup_res = self.client.post('/api/settings/roles', json=custom_role_payload)
        self.assertEqual(dup_res.status_code, 400)

        # 4. Update the custom role
        update_payload = {
            "role_name": "Weekend Senior Lead",
            "description": "Updated shift lead description",
            "permissions": ["billing:read", "billing:write", "billing:discount", "appointments:read", "appointments:write", "customers:read"]
        }
        res = self.client.patch(f'/api/settings/roles/{created_role_id}', json=update_payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # 5. Owner Lockout Protection: Test stripping accounts:write or billing:write from Owner role
        owner_role = next(r for r in roles if r['is_system_locked'])
        lockout_payload = {
            "role_name": owner_role['role_name'],
            "description": owner_role['description'],
            "permissions": ["billing:read"] # Omitted accounts:write and billing:write
        }
        res = self.client.patch(f'/api/settings/roles/{owner_role["id"]}', json=lockout_payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Owner Lockout Protection", res.get_json()['message'])

        # 6. Test system role deletion protection
        res = self.client.delete(f'/api/settings/roles/{owner_role["id"]}')
        self.assertEqual(res.status_code, 400)
        self.assertIn("System-critical", res.get_json()['message'])

        # 7. Add account with the custom role
        acc_payload = {
            "email": "shiftlead@aurasalon.com",
            "password": "Password123!",
            "role_id": created_role_id
        }
        res = self.client.post('/api/settings/accounts', json=acc_payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify account has role_id
        res = self.client.get('/api/settings/accounts')
        self.assertEqual(res.status_code, 200)
        accs = res.get_json()['accounts']
        lead_acc = next(a for a in accs if a['username'] == 'shiftlead@aurasalon.com')
        self.assertEqual(lead_acc['role_id'], created_role_id)
        self.assertEqual(lead_acc['role_name'], "Weekend Senior Lead")

        # 8. Deletion with active members check (Reassignment requirement)
        del_res = self.client.delete(f'/api/settings/roles/{created_role_id}')
        self.assertEqual(del_res.status_code, 400)
        self.assertTrue(del_res.get_json().get('requires_reassignment'))

        # Delete with reassignment to Manager or Billing Desk
        billing_desk_role = next(r for r in roles if r['role_name'] == 'Billing Desk')
        del_reassign_res = self.client.delete(f'/api/settings/roles/{created_role_id}', json={"reassign_to": billing_desk_role['id']})
        self.assertEqual(del_reassign_res.status_code, 200)
        self.assertTrue(del_reassign_res.get_json()['success'])

        # Verify lead account was reassigned
        res = self.client.get('/api/settings/accounts')
        lead_acc_after = next(a for a in res.get_json()['accounts'] if a['username'] == 'shiftlead@aurasalon.com')
        self.assertEqual(lead_acc_after['role_id'], billing_desk_role['id'])

        # Clean up created account
        self.client.delete(f'/api/settings/accounts/{lead_acc_after["id"]}')

    def test_tax_master_api_and_billing(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. GET Tax Master settings
        res = self.client.get('/api/settings/taxes')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('tax_settings', data)
        tax = data['tax_settings']
        self.assertIn('tax_name', tax)
        self.assertIn('tax_rate', tax)

        # 2. Update Tax Master settings
        update_payload = {
            "tax_settings": {
                "enabled": True,
                "tax_name": "GST",
                "tax_rate": 18.0,
                "tax_type": "exclusive",
                "tax_number": "27AAPFU0939F1ZV",
                "split_tax": True
            }
        }
        res = self.client.put('/api/settings/taxes', json=update_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['tax_settings']['tax_rate'], 18.0)
        self.assertEqual(data['tax_settings']['tax_number'], "27AAPFU0939F1ZV")

        # 3. Create a bill with the configured tax rate
        subtotal = 1000
        discount = 100
        taxable = subtotal - discount
        calc_tax = round(taxable * 0.18)
        grand_total = taxable + calc_tax

        bill_payload = {
            "client_name": "Deepika Rao",
            "client_phone": "9988776655",
            "subtotal": subtotal,
            "discount": discount,
            "tax": calc_tax,
            "grand_total": grand_total,
            "payment_mode": "UPI",
            "items": [{"name": "Hair Smoothing", "price": 1000, "qty": 1}]
        }
        res = self.client.post('/api/bills', json=bill_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('bill_id', data)

    def test_staff_mass_upload_and_template(self):
        # Set salon plan to studio for mass upload access
        authRepo.update_salon_plan(1, "studio", "monthly", int(datetime.now().timestamp()) + 86400 * 30)

        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. Download Staff CSV Template
        res = self.client.get('/api/settings/export/template/staff')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"name", res.data)
        self.assertIn(b"role", res.data)
        self.assertIn(b"phone", res.data)

        # 2. Export Staff CSV
        res = self.client.get('/api/settings/export/staff')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/csv; charset=utf-8")

        # 3. Mass upload valid staff
        stamp = str(uuid4())[:8]
        name1 = f"Test Stylist Alpha {stamp}"
        name2 = f"Test Stylist Beta {stamp}"
        csv_data = f"name,role,phone,gender,email\n{name1},Senior Stylist,9111222333,Male,alpha@aurasalon.com\n{name2},Colorist,9222333444,Female,beta@aurasalon.com\n"
        data = {
            'file': (io.BytesIO(csv_data.encode('utf-8')), 'staff.csv')
        }
        res = self.client.post('/api/settings/import/staff', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        result = res.get_json()
        self.assertTrue(result['success'])
        self.assertEqual(result['added'], 2)

        # 4. Upload duplicate staff (should skip duplicate names)
        data_dup = {
            'file': (io.BytesIO(csv_data.encode('utf-8')), 'staff.csv')
        }
        res = self.client.post('/api/settings/import/staff', data=data_dup, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        result_dup = res.get_json()
        self.assertEqual(result_dup['added'], 0)
        self.assertEqual(result_dup['skipped'], 2)

    def test_invoices_mass_upload_and_template(self):
        # Set salon plan to studio
        authRepo.update_salon_plan(1, "studio", "monthly", int(datetime.now().timestamp()) + 86400 * 30)

        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. Download Invoices CSV Template
        res = self.client.get('/api/settings/export/template/invoices')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"subtotal", res.data)
        self.assertIn(b"payment_mode", res.data)

        # 2. Export Invoices
        res = self.client.get('/api/settings/export/bills')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/csv; charset=utf-8")

        # 3. Mass upload valid invoices
        stamp = str(uuid4())[:6].upper()
        inv1 = f"AP-T{stamp}1"
        inv2 = f"AP-T{stamp}2"
        invoice_csv = (
            "id,client_name,client_phone,subtotal,discount,tax,grand_total,payment_mode,items,created_at\n"
            f"{inv1},Imported Client 1,9888877771,1500,100,252,1652,UPI,\"Haircut, Spa\",2026-10-01\n"
            f"{inv2},Imported Client 2,9888877772,800,0,144,944,Cash,\"Beard Trim\",2026-10-02\n"
        )
        data = {
            'file': (io.BytesIO(invoice_csv.encode('utf-8')), 'invoices.csv')
        }
        res = self.client.post('/api/settings/import/invoices', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        result = res.get_json()
        self.assertTrue(result['success'])
        self.assertEqual(result['added'], 2)

        # 4. Upload duplicate invoices (should skip duplicate IDs)
        data_dup = {
            'file': (io.BytesIO(invoice_csv.encode('utf-8')), 'invoices.csv')
        }
        res = self.client.post('/api/settings/import/invoices', data=data_dup, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        result_dup = res.get_json()
        self.assertEqual(result_dup['added'], 0)
        self.assertEqual(result_dup['skipped'], 2)
        self.assertEqual(result_dup['added'], 0)
        self.assertEqual(result_dup['skipped'], 2)


if __name__ == '__main__':
    unittest.main()



