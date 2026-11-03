import unittest
import json
import io
from datetime import datetime
from uuid import uuid4
from app import app, authRepo, billRepo, staffRepo, reportRepo

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
        authRepo.update_salon_plan(1, "studio", "yearly", int(datetime.now().timestamp()) + 86400 * 365)
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
        role_tag = uuid4().hex[:6]
        role_name_1 = f"Shift Lead {role_tag}"
        role_name_2 = f"Senior Lead {role_tag}"
        custom_role_payload = {
            "role_name": role_name_1,
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
            "role_name": role_name_2,
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
        unique_email = f"shiftlead_{uuid4().hex[:6]}@aurasalon.com"
        acc_payload = {
            "email": unique_email,
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
        lead_acc = next(a for a in accs if a['username'] == unique_email)
        self.assertEqual(lead_acc['role_id'], created_role_id)
        self.assertEqual(lead_acc['role_name'], role_name_2)

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
        lead_acc_after = next(a for a in res.get_json()['accounts'] if a['username'] == unique_email)
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

    def test_billing_editable_price_and_inclusive_tax(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # Test line item with custom edited price & tax inclusive calculation
        # Subtotal: 1000, Discount: 0, Tax Inclusive 18% -> grand_total MUST be 1000
        # Taxable amount = 1000 / 1.18 = 847.46, Tax = 152.54
        payload = {
            'client_name': 'Aarav Mehta',
            'client_phone': '9811122233',
            'subtotal': 1000,
            'discount': 0,
            'tax': 153,
            'grand_total': 1000,  # Grand total does not increase when tax is inclusive
            'tax_enabled': True,
            'tax_inclusive': True,
            'tax_rate': 18.0,
            'tax_amount': 153,
            'amount_paid': 1000,
            'payment_mode': 'UPI',
            'items': [
                {
                    'name': 'Custom Styled Haircut',
                    'price': 1000,
                    'catalog_price': 1200,  # Edited down from 1200
                    'qty': 1,
                    'staff': 'Alex Rivera'
                }
            ]
        }
        res = self.client.post('/api/bills', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['grand_total'], 1000)
        self.assertEqual(data.get('payment_status'), 'PAID')

    def test_part_payments_and_due_recoverable_flow(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        test_phone = f"99{str(uuid4().int)[:8]}"

        # 1. Create a bill with part payment: Grand total 3000, Paid 1000, Due 2000
        bill_payload = {
            'client_name': 'Meera Kapoor',
            'client_phone': test_phone,
            'subtotal': 3000,
            'discount': 0,
            'tax': 0,
            'grand_total': 3000,
            'amount_paid': 1000,
            'payment_mode': 'Cash',
            'items': [
                {'name': 'Balayage Color', 'price': 3000, 'qty': 1, 'staff': 'Priya Nair'}
            ]
        }
        res = self.client.post('/api/bills', json=bill_payload)
        self.assertEqual(res.status_code, 200)
        created = res.get_json()
        bill_id = created['bill_id']
        self.assertEqual(created['due_amount'], 2000)
        self.assertEqual(created['payment_status'], 'PARTIALLY_PAID')

        # 2. Check customer outstanding dues API
        res_dues = self.client.get(f'/api/customers/{test_phone}/dues')
        self.assertEqual(res_dues.status_code, 200)
        dues_data = res_dues.get_json()
        self.assertEqual(dues_data['total_due'], 2000)
        self.assertTrue(any(d['id'] == bill_id for d in dues_data['dues']))

        # 3. Check bill payment history
        res_history = self.client.get(f'/api/bills/{bill_id}/payments')
        self.assertEqual(res_history.status_code, 200)
        payments_data = res_history.get_json()
        self.assertEqual(len(payments_data['payments']), 1)
        self.assertEqual(payments_data['payments'][0]['amount'], 1000)

        # 4. Settle another part payment of ₹1500
        pay_res = self.client.post(f'/api/bills/{bill_id}/pay', json={
            'amount': 1500,
            'payment_mode': 'UPI',
            'notes': 'Online settlement'
        })
        self.assertEqual(pay_res.status_code, 200)
        pay_data = pay_res.get_json()
        self.assertTrue(pay_data['success'])
        self.assertEqual(pay_data['bill']['amount_paid'], 2500)
        self.assertEqual(pay_data['bill']['due_amount'], 500)
        self.assertEqual(pay_data['bill']['payment_status'], 'PARTIALLY_PAID')

        # 5. Settle the remaining ₹500 to fully clear the bill
        pay_final = self.client.post(f'/api/bills/{bill_id}/pay', json={
            'amount': 500,
            'payment_mode': 'Cash',
            'notes': 'Full clearance'
        })
        self.assertEqual(pay_final.status_code, 200)
        final_data = pay_final.get_json()
        self.assertEqual(final_data['bill']['amount_paid'], 3000)
        self.assertEqual(final_data['bill']['due_amount'], 0)
        self.assertEqual(final_data['bill']['payment_status'], 'PAID')

        # 6. Verify customer dues are now 0
        res_dues_after = self.client.get(f'/api/customers/{test_phone}/dues')
        self.assertEqual(res_dues_after.get_json()['total_due'], 0)

    def test_staff_revenue_split_attribution(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # Bill with 2 stylists sharing attribution on a line item
        split_bill = {
            'client_name': 'Kavita Singh',
            'client_phone': '9822233344',
            'subtotal': 2000,
            'discount': 0,
            'tax': 0,
            'grand_total': 2000,
            'amount_paid': 2000,
            'payment_mode': 'Card',
            'items': [
                {
                    'name': 'Keratin Therapy',
                    'price': 2000,
                    'qty': 1,
                    'staff': 'Alex Rivera',
                    'staff_split': {
                        'enabled': True,
                        'stylist1': 'Alex Rivera',
                        'ratio1': 60,
                        'stylist2': 'Priya Nair',
                        'ratio2': 40
                    }
                }
            ]
        }
        res = self.client.post('/api/bills', json=split_bill)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        # Leaderboard should reflect both stylists receiving attribution
        now_ts = int(datetime.now().timestamp())
        leaderboard = reportRepo.staff_leaderboard(1, 0, now_ts + 3600)
        stylist_names = [st['name'] for st in leaderboard]
        self.assertIn('Alex Rivera', stylist_names)
        self.assertIn('Priya Nair', stylist_names)

    def test_printer_and_whatsapp_settings_api(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. Printer settings
        printer_update = {
            'paper_width': '2inch',
            'auto_cut': True,
            'header_text': 'Welcome to Aura',
            'footer_text': 'Visit again!'
        }
        p_res = self.client.post('/api/settings/printer', json=printer_update)
        self.assertEqual(p_res.status_code, 200)
        p_data = p_res.get_json()
        self.assertTrue(p_data['success'])
        self.assertEqual(p_data['printer_settings']['paper_width'], '2inch')

        # Read back printer settings
        p_get = self.client.get('/api/settings/printer')
        self.assertEqual(p_get.status_code, 200)
        self.assertEqual(p_get.get_json()['printer_settings']['paper_width'], '2inch')

        # 2. WhatsApp settings
        whatsapp_update = {
            'enabled': True,
            'provider': 'mock',
            'sender_phone': '+91 9988776655',
            'template_id': 'booking_confirmation'
        }
        w_res = self.client.post('/api/settings/whatsapp', json=whatsapp_update)
        self.assertEqual(w_res.status_code, 200)
        w_data = w_res.get_json()
        self.assertTrue(w_data['success'])
        self.assertEqual(w_data['whatsapp_settings']['sender_phone'], '+91 9988776655')

        # Read back WhatsApp settings
        w_get = self.client.get('/api/settings/whatsapp')
        self.assertEqual(w_get.status_code, 200)
        self.assertEqual(w_get.get_json()['whatsapp_settings']['sender_phone'], '+91 9988776655')

    def test_public_booking_with_whatsapp_confirmation(self):
        # Public booking endpoint sends booking and triggers WhatsApp confirmation dispatcher
        booking_payload = {
            'salon_id': 1,
            'name': 'Tanvi Sharma',
            'phone': '9876501234',
            'email': 'tanvi@example.com',
            'service': 'Express Blow Dry + Head Massage',
            'slot': '11:00 AM',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'stylist': 'Alex Rivera',
            'price': 1500,
            'duration': 60,
            'notes': 'Allergic to strong fragrances'
        }
        res = self.client.post('/api/public/booking', json=booking_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('booking_id', data)

    def test_product_inventory_and_billing_decrement(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. Create a retail product
        prod_payload = {
            'name': 'Moroccan Argan Hair Serum',
            'category': 'Hair Care',
            'brand': 'Moroccanoil',
            'sku': 'MOR-SERUM-100',
            'price': 1800,
            'cost_price': 1100,
            'stock_quantity': 15,
            'tax_rate': 18,
            'barcode': '8901234567890'
        }
        res = self.client.post('/api/products', json=prod_payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        prod_id = data['product']['id']
        self.assertEqual(data['product']['stock_quantity'], 15)

        # 2. Adjust stock
        res = self.client.post(f'/api/products/{prod_id}/stock', json={'adjustment': 5, 'reason': 'Restock batch'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['product']['stock_quantity'], 20)

        # 3. Sell product on invoice and verify inventory decrement
        bill_payload = {
            'terminal_id': '01',
            'client_name': 'Aarav Mehta',
            'client_phone': '9811122334',
            'subtotal': 3600,
            'discount': 0,
            'tax': 648,
            'grand_total': 4248,
            'amount_paid': 4248,
            'due_amount': 0,
            'payment_status': 'PAID',
            'payment_mode': 'UPI',
            'tax_enabled': True,
            'tax_inclusive': False,
            'tax_rate': 18,
            'items': [
                {
                    'id': prod_id,
                    'product_id': prod_id,
                    'name': 'Moroccan Argan Hair Serum',
                    'type': 'product',
                    'price': 1800,
                    'qty': 2,
                    'tax_rate': 18,
                    'staff': 'Alex Rivera'
                }
            ]
        }
        b_res = self.client.post('/api/bills', json=bill_payload)
        self.assertEqual(b_res.status_code, 200)
        self.assertTrue(b_res.get_json()['success'])

        # Verify stock decreased from 20 to 18
        p_res = self.client.get('/api/products')
        self.assertEqual(p_res.status_code, 200)
        products = p_res.get_json()['products']
        p_item = next((p for p in products if p['id'] == prod_id), None)
        self.assertIsNotNone(p_item)
        self.assertEqual(p_item['stock_quantity'], 18)

    def test_membership_tier_management_and_bill_activation(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        suffix1 = str(int(datetime.now().timestamp()))[-6:]
        phone1 = f"98{suffix1}11"
        phone2 = f"98{suffix1}22"

        # 1. Create a customer
        c_res = self.client.post('/api/customers', json={
            'name': 'Pooja Hegde',
            'phone': phone1,
            'email': f'pooja_{suffix1}@example.com'
        })
        self.assertIn(c_res.status_code, [200, 201])
        c_data = c_res.get_json()
        cust_id = c_data['customer']['id'] if 'customer' in c_data else c_data['id']

        # 2. Create a membership tier
        tier_payload = {
            'name': f'Platinum VIP Privilege {suffix1}',
            'price': 5000,
            'validity_days': 180,
            'service_discount_pct': 20,
            'product_discount_pct': 15,
            'perks': ['20% discount on all salon services', '15% discount on retail products', 'Free scalp spa analysis on birthdays'],
            'description': 'Exclusive high-tier membership for premium clients'
        }
        t_res = self.client.post('/api/memberships/tiers', json=tier_payload)
        self.assertEqual(t_res.status_code, 201)
        tier_id = t_res.get_json()['tier']['id']

        # 3. Direct assignment to customer
        assign_res = self.client.post(f'/api/customers/{cust_id}/membership', json={'tier_id': tier_id})
        self.assertEqual(assign_res.status_code, 200)
        self.assertTrue(assign_res.get_json()['success'])

        # Read back customer membership
        mem_check = self.client.get(f'/api/customers/{cust_id}/membership')
        self.assertEqual(mem_check.status_code, 200)
        check_data = mem_check.get_json()
        self.assertTrue(check_data['has_membership'])
        self.assertEqual(check_data['active_membership']['tier_id'], tier_id)
        self.assertEqual(check_data['active_membership']['service_discount_pct'], 20)

        # 4. Sell membership via invoice to another customer and test auto-assignment
        c2_res = self.client.post('/api/customers', json={
            'name': 'Kavya Nair',
            'phone': phone2,
            'email': f'kavya_{suffix1}@example.com'
        })
        self.assertIn(c2_res.status_code, [200, 201])
        c2_data = c2_res.get_json()
        cust2_id = c2_data['customer']['id'] if 'customer' in c2_data else c2_data['id']

        # Sell membership in bill
        bill_mem_payload = {
            'terminal_id': '01',
            'client_name': 'Kavya Nair',
            'client_phone': phone2,
            'subtotal': 5000,
            'discount': 0,
            'tax': 0,
            'grand_total': 5000,
            'amount_paid': 5000,
            'due_amount': 0,
            'payment_status': 'PAID',
            'payment_mode': 'Card',
            'tax_enabled': False,
            'tax_inclusive': False,
            'tax_rate': 0,
            'items': [
                {
                    'id': tier_id,
                    'tier_id': tier_id,
                    'name': 'Platinum VIP Privilege Membership',
                    'type': 'membership',
                    'price': 5000,
                    'qty': 1,
                    'staff': 'Unassigned'
                }
            ]
        }
        b_res = self.client.post('/api/bills', json=bill_mem_payload)
        self.assertEqual(b_res.status_code, 200)
        self.assertTrue(b_res.get_json()['success'])

        # Verify customer #2 now has active membership
        mem2_check = self.client.get(f'/api/customers/{cust2_id}/membership')
        self.assertEqual(mem2_check.status_code, 200)
        check2_data = mem2_check.get_json()
        self.assertTrue(check2_data['has_membership'])
        self.assertEqual(check2_data['active_membership']['tier_id'], tier_id)
        self.assertEqual(check2_data['active_membership']['tier_name'], tier_payload['name'])

    def test_reports_csv_exports_and_staff_splits(self):
        with self.client.session_transaction() as sess:
            sess['id'] = 1
            sess['username'] = 'admin'
            sess['auth_level'] = 'admin'

        # 1. Create a bill with split staff on service, product, and membership
        split_items_bill = {
            'client_name': 'Meera Kapoor',
            'client_phone': '9812345678',
            'subtotal': 4500,
            'discount': 0,
            'tax': 0,
            'grand_total': 4500,
            'amount_paid': 4500,
            'payment_mode': 'UPI',
            'items': [
                {
                    'name': 'Balayage Hair Color',
                    'type': 'service',
                    'price': 2000,
                    'qty': 1,
                    'staff': 'Rohan, Priya',
                    'staff_split': {
                        'enabled': True,
                        'stylist1': 'Rohan',
                        'ratio1': 60,
                        'stylist2': 'Priya',
                        'ratio2': 40
                    }
                },
                {
                    'name': 'Moroccan Argan Shampoo',
                    'type': 'product',
                    'price': 1000,
                    'qty': 1,
                    'staff': 'Rohan, Sonia',
                    'staff_split': {
                        'enabled': True,
                        'stylist1': 'Rohan',
                        'ratio1': 50,
                        'stylist2': 'Sonia',
                        'ratio2': 50
                    }
                },
                {
                    'name': 'Gold VIP Membership',
                    'type': 'membership',
                    'price': 1500,
                    'qty': 1,
                    'staff': 'Priya, Sonia',
                    'staff_split': {
                        'enabled': True,
                        'stylist1': 'Priya',
                        'ratio1': 70,
                        'stylist2': 'Sonia',
                        'ratio2': 30
                    }
                }
            ]
        }
        res = self.client.post('/api/bills', json=split_items_bill)
        self.assertEqual(res.status_code, 200)
        b_data = res.get_json()
        self.assertTrue(b_data['success'])

        # 2. Test Invoices & Recoverables CSV Export
        inv_res = self.client.get('/api/reports/export/invoices-csv')
        self.assertEqual(inv_res.status_code, 200)
        self.assertEqual(inv_res.mimetype, 'text/csv')
        csv_text = inv_res.data.decode('utf-8')
        lines = [line.strip() for line in csv_text.splitlines() if line.strip()]
        self.assertTrue(len(lines) >= 2)
        expected_header = 'sno,bill-id,product_name,price,staff(comma separated if mulitple),date,time'
        self.assertEqual(lines[0].replace('"', ''), expected_header)
        # Verify comma-separated staff appears in line items
        self.assertTrue(any('Rohan, Priya' in line for line in lines))

        # 3. Test Staff Data CSV Export
        staff_res = self.client.get('/api/reports/export/staff-csv')
        self.assertEqual(staff_res.status_code, 200)
        self.assertEqual(staff_res.mimetype, 'text/csv')
        staff_csv_text = staff_res.data.decode('utf-8')
        # Verify per-staff sheet header and table headers
        self.assertIn('sno,bill-id,service_name,contribution,date,time', staff_csv_text.replace('"', ''))
        self.assertTrue('Sheet: Rohan' in staff_csv_text or 'Sheet:' in staff_csv_text)


if __name__ == '__main__':
    unittest.main()





