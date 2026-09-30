import unittest
import json
from app import app, authRepo, billRepo

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
        self.assertIn(b"aurapos3.vercel.app", res.data)

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

if __name__ == '__main__':
    unittest.main()

