SET session_replication_role = replica;

--
-- PostgreSQL database dump
--

-- \restrict gJJJEvj3K7WcK3Em282RO3xblxJZXRoXgQNwrhNdSxxWn6e6YF55aBcmJQ0Tduv

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: salons; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."salons" ("id", "name", "phone", "salon_name", "email", "created_on", "plan", "expires_on", "logo", "billing_cycle", "address", "opening_hours", "latitude", "longitude", "booking_slug") VALUES
	(1, 'Salon Owner', '9876543210', 'Aura Studio Elite', 'admin@aurasalon.com', 1790760279, 'studio', 1822296279, NULL, 'yearly', '402 High Street Mall, Indiranagar, Bengaluru', '{"monday": {"open": "09:00", "close": "21:00", "isOpen": true}, "tuesday": {"open": "09:00", "close": "21:00", "isOpen": true}, "wednesday": {"open": "09:00", "close": "21:00", "isOpen": true}, "thursday": {"open": "09:00", "close": "21:00", "isOpen": true}, "friday": {"open": "09:00", "close": "21:00", "isOpen": true}, "saturday": {"open": "09:00", "close": "21:00", "isOpen": true}, "sunday": {"open": "10:00", "close": "18:00", "isOpen": false}}', 12.9716, 77.5946, '7bfqn');


--
-- Data for Name: accounts; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."accounts" ("id", "auth_id", "username", "password", "auth_level") VALUES
	(1, 1, 'admin@aurasalon.com', 'password', 'admin');


--
-- Data for Name: app_settings; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."app_settings" ("key", "value", "updated_at") VALUES
	('accepting_public', 'true', 1790760279);


--
-- Data for Name: appointments; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."appointments" ("id", "account_id", "client", "phone", "email", "service", "time", "date", "staff", "price", "duration", "status", "notes") VALUES
	(1, 1, 'Shreya Gupta', '9828728463', 'shreya.gupta23@gmail.com', 'Women''s Layer Cut & Blowdry', '03:30 PM', '2026-09-23', 'Marcus Vance', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(2, 1, 'Varun Mukherjee', '9897226012', 'varun.mukherjee99@gmail.com', 'Luxury Organic Hair Spa', '10:00 AM', '2026-09-25', 'Priya Nair', 1150, 50, 'Completed', 'Booked via POS & Online Portal'),
	(3, 1, 'Meera Joshi', '9855176955', 'meera.joshi23@gmail.com', 'Women''s Layer Cut & Blowdry', '03:30 PM', '2026-09-20', 'Priya Nair', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(4, 1, 'Sneha Deshmukh', '9820576383', 'sneha.deshmukh80@gmail.com', 'Royal Beard Sculpt & Hot Towel', '07:15 PM', '2026-09-14', 'Marcus Vance', 413, 25, 'Completed', 'Booked via POS & Online Portal'),
	(5, 1, 'Karan Rao', '9861019678', 'karan.rao45@gmail.com', 'Royal Beard Sculpt & Hot Towel', '11:15 AM', '2026-09-28', 'Alex Rivera', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(6, 1, 'Shreya Iyer', '9872043515', 'shreya.iyer58@gmail.com', 'Luxury Organic Hair Spa', '12:30 PM', '2026-09-13', 'Marcus Vance', 1150, 50, 'Completed', 'Booked via POS & Online Portal'),
	(7, 1, 'Tanvi Roy', '9838317637', 'tanvi.roy82@gmail.com', 'Royal Beard Sculpt & Hot Towel + Women''s Layer Cut & Blowdry', '06:00 PM', '2026-09-16', 'Marcus Vance', 1000, 25, 'Completed', 'Booked via POS & Online Portal'),
	(8, 1, 'Shreya Bose', '9885345555', 'shreya.bose78@gmail.com', 'Keratin Smooth Treatment', '12:30 PM', '2026-09-01', 'Marcus Vance', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(9, 1, 'Sneha Verma', '9894214382', 'sneha.verma30@gmail.com', 'Keratin Smooth Treatment + Full Balayage & Toning', '10:00 AM', '2026-08-29', 'Alex Rivera', 7600, 90, 'Completed', 'Booked via POS & Online Portal'),
	(10, 1, 'Sneha Sharma', '9882070937', 'sneha.sharma44@gmail.com', 'Royal Beard Sculpt & Hot Towel + Signature Haircut & Wash', '10:00 AM', '2026-08-28', 'Priya Nair', 800, 25, 'Completed', 'Booked via POS & Online Portal'),
	(11, 1, 'Rahul Sen', '9850056581', 'rahul.sen91@gmail.com', 'Luxury Organic Hair Spa', '12:30 PM', '2026-09-30', 'Alex Rivera', 1150, 50, 'Confirmed', 'Booked via POS & Online Portal'),
	(12, 1, 'Sneha Saxena', '9851273847', 'sneha.saxena40@gmail.com', 'Women''s Layer Cut & Blowdry', '10:00 AM', '2026-09-30', 'Alex Rivera', 750, 45, 'Confirmed', 'Booked via POS & Online Portal'),
	(13, 1, 'Arjun Nair', '9880823176', 'arjun.nair87@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-09-22', 'Marcus Vance', 1200, 50, 'Completed', 'Booked via POS & Online Portal'),
	(14, 1, 'Sneha Gupta', '9840158366', 'sneha.gupta18@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-09-07', 'Marcus Vance', 1416, 50, 'Completed', 'Booked via POS & Online Portal'),
	(15, 1, 'Ishita Roy', '9879008866', 'ishita.roy40@gmail.com', 'Express Blowdry & Styling', '10:00 AM', '2026-09-27', 'Alex Rivera', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(16, 1, 'Varun Rao', '9823009833', 'varun.rao94@gmail.com', 'Keratin Smooth Treatment', '06:00 PM', '2026-08-31', 'Priya Nair', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(17, 1, 'Rahul Gupta', '9835714784', 'rahul.gupta34@gmail.com', 'Hydra-Dew Glow Facial', '04:45 PM', '2026-09-24', 'Priya Nair', 1770, 60, 'Completed', 'Booked via POS & Online Portal'),
	(18, 1, 'Kavita Sen', '9882556484', 'kavita.sen11@gmail.com', 'Luxury Organic Hair Spa + Women''s Layer Cut & Blowdry', '11:15 AM', '2026-09-26', 'Priya Nair', 1850, 50, 'Completed', 'Booked via POS & Online Portal'),
	(19, 1, 'Amit Nair', '9871070189', 'amit.nair46@gmail.com', 'Express Blowdry & Styling', '10:00 AM', '2026-09-27', 'Alex Rivera', 590, 30, 'Completed', 'Booked via POS & Online Portal'),
	(20, 1, 'Kavita Mehta', '9888406989', 'kavita.mehta71@gmail.com', 'Hydra-Dew Glow Facial', '04:45 PM', '2026-09-27', 'Alex Rivera', 1500, 60, 'Completed', 'Booked via POS & Online Portal'),
	(21, 1, 'Shreya Aggarwal', '9889795010', 'shreya.aggarwal15@gmail.com', 'Keratin Smooth Treatment', '11:15 AM', '2026-09-26', 'Marcus Vance', 4450, 90, 'Completed', 'Booked via POS & Online Portal'),
	(22, 1, 'Manish Sharma', '9896637649', 'manish.sharma48@gmail.com', 'Women''s Layer Cut & Blowdry', '06:00 PM', '2026-09-10', 'Alex Rivera', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(23, 1, 'Akash Verma', '9856843172', 'akash.verma18@gmail.com', 'Royal Beard Sculpt & Hot Towel + Hydra-Dew Glow Facial', '02:00 PM', '2026-09-24', 'Alex Rivera', 1750, 25, 'Completed', 'Booked via POS & Online Portal'),
	(24, 1, 'Rahul Verma', '9845496015', 'rahul.verma24@gmail.com', 'Hydra-Dew Glow Facial + Express Blowdry & Styling', '03:30 PM', '2026-09-11', 'Priya Nair', 2000, 60, 'Completed', 'Booked via POS & Online Portal'),
	(25, 1, 'Pooja Sen', '9866851377', 'pooja.sen45@gmail.com', 'Royal Beard Sculpt & Hot Towel', '10:00 AM', '2026-09-14', 'Alex Rivera', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(26, 1, 'Rohan Rao', '9820099059', 'rohan.rao98@gmail.com', 'Signature Haircut & Wash + Keratin Smooth Treatment', '06:00 PM', '2026-09-20', 'Priya Nair', 4950, 35, 'Completed', 'Booked via POS & Online Portal'),
	(27, 1, 'Rhea Sharma', '9843491314', 'rhea.sharma95@gmail.com', 'Keratin Smooth Treatment', '04:45 PM', '2026-09-11', 'Marcus Vance', 4500, 90, 'Completed', 'Booked via POS & Online Portal'),
	(28, 1, 'Divya Bose', '9854585178', 'divya.bose62@gmail.com', 'Luxury Organic Hair Spa + Hydra-Dew Glow Facial', '10:00 AM', '2026-09-20', 'Alex Rivera', 2700, 50, 'Completed', 'Booked via POS & Online Portal'),
	(29, 1, 'Gaurav Reddy', '9840547349', 'gaurav.reddy38@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-08-31', 'Priya Nair', 1357, 50, 'Completed', 'Booked via POS & Online Portal'),
	(30, 1, 'Ishita Kapoor', '9825480907', 'ishita.kapoor43@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-09-13', 'Alex Rivera', 3200, 120, 'Completed', 'Booked via POS & Online Portal'),
	(31, 1, 'Amit Aggarwal', '9835511941', 'amit.aggarwal42@gmail.com', 'Keratin Smooth Treatment', '11:15 AM', '2026-09-10', 'Alex Rivera', 4500, 90, 'Completed', 'Booked via POS & Online Portal'),
	(32, 1, 'Ananya Kulkarni', '9851511484', 'ananya.kulkarni95@gmail.com', 'Keratin Smooth Treatment', '11:15 AM', '2026-09-09', 'Marcus Vance', 4450, 90, 'Completed', 'Booked via POS & Online Portal'),
	(33, 1, 'Ananya Deshmukh', '9883542887', 'ananya.deshmukh10@gmail.com', 'Luxury Organic Hair Spa', '12:30 PM', '2026-09-04', 'Priya Nair', 1150, 50, 'Completed', 'Booked via POS & Online Portal'),
	(34, 1, 'Pooja Reddy', '9879182797', 'pooja.reddy94@gmail.com', 'Royal Beard Sculpt & Hot Towel', '12:30 PM', '2026-09-17', 'Alex Rivera', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(35, 1, 'Neha Mehta', '9842862209', 'neha.mehta70@gmail.com', 'Women''s Layer Cut & Blowdry', '12:30 PM', '2026-09-11', 'Priya Nair', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(36, 1, 'Shreya Verma', '9898054615', 'shreya.verma98@gmail.com', 'Women''s Layer Cut & Blowdry', '06:00 PM', '2026-09-18', 'Priya Nair', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(37, 1, 'Sneha Bhatia', '9827896471', 'sneha.bhatia69@gmail.com', 'Royal Beard Sculpt & Hot Towel', '02:00 PM', '2026-08-28', 'Priya Nair', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(38, 1, 'Arjun Bose', '9873709724', 'arjun.bose67@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-08-29', 'Marcus Vance', 1150, 50, 'Completed', 'Booked via POS & Online Portal'),
	(39, 1, 'Aditya Mukherjee', '9848349783', 'aditya.mukherjee40@gmail.com', 'Royal Beard Sculpt & Hot Towel', '07:15 PM', '2026-08-30', 'Marcus Vance', 413, 25, 'Completed', 'Booked via POS & Online Portal'),
	(40, 1, 'Rhea Roy', '9865682626', 'rhea.roy62@gmail.com', 'Express Blowdry & Styling', '12:30 PM', '2026-09-16', 'Priya Nair', 590, 30, 'Completed', 'Booked via POS & Online Portal'),
	(41, 1, 'Rajesh Kapoor', '9857212267', 'rajesh.kapoor48@gmail.com', 'Keratin Smooth Treatment + Full Balayage & Toning', '06:00 PM', '2026-09-06', 'Marcus Vance', 7700, 90, 'Completed', 'Booked via POS & Online Portal'),
	(42, 1, 'Ishita Sharma', '9864266464', 'ishita.sharma31@gmail.com', 'Hydra-Dew Glow Facial + Full Balayage & Toning', '06:00 PM', '2026-09-03', 'Marcus Vance', 4700, 60, 'Completed', 'Booked via POS & Online Portal'),
	(43, 1, 'Manish Bhatia', '9834391257', 'manish.bhatia16@gmail.com', 'Royal Beard Sculpt & Hot Towel', '06:00 PM', '2026-09-29', 'Alex Rivera', 350, 25, 'Confirmed', 'Booked via POS & Online Portal'),
	(44, 1, 'Rajesh Kapoor', '9882399599', 'rajesh.kapoor16@gmail.com', 'Royal Beard Sculpt & Hot Towel + Women''s Layer Cut & Blowdry', '11:15 AM', '2026-09-13', 'Marcus Vance', 1100, 25, 'Completed', 'Booked via POS & Online Portal'),
	(45, 1, 'Neha Patel', '9830452412', 'neha.patel40@gmail.com', 'Women''s Layer Cut & Blowdry', '02:00 PM', '2026-09-28', 'Marcus Vance', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(46, 1, 'Arjun Reddy', '9824508768', 'arjun.reddy84@gmail.com', 'Full Balayage & Toning', '11:15 AM', '2026-09-14', 'Marcus Vance', 3100, 120, 'Completed', 'Booked via POS & Online Portal'),
	(47, 1, 'Rahul Mukherjee', '9850477742', 'rahul.mukherjee97@gmail.com', 'Women''s Layer Cut & Blowdry', '02:00 PM', '2026-09-18', 'Marcus Vance', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(48, 1, 'Aditya Kulkarni', '9896911784', 'aditya.kulkarni53@gmail.com', 'Keratin Smooth Treatment', '04:45 PM', '2026-08-27', 'Priya Nair', 4500, 90, 'Completed', 'Booked via POS & Online Portal'),
	(49, 1, 'Tanvi Patel', '9882232344', 'tanvi.patel71@gmail.com', 'Full Balayage & Toning', '12:30 PM', '2026-09-01', 'Priya Nair', 3200, 120, 'Completed', 'Booked via POS & Online Portal'),
	(50, 1, 'Amit Chopra', '9813852048', 'amit.chopra73@gmail.com', 'Hydra-Dew Glow Facial + Luxury Organic Hair Spa', '07:15 PM', '2026-09-13', 'Alex Rivera', 2650, 60, 'Completed', 'Booked via POS & Online Portal'),
	(51, 1, 'Varun Roy', '9842394260', 'varun.roy62@gmail.com', 'Luxury Organic Hair Spa', '10:00 AM', '2026-09-13', 'Marcus Vance', 1100, 50, 'Completed', 'Booked via POS & Online Portal'),
	(52, 1, 'Karan Deshmukh', '9842655866', 'karan.deshmukh49@gmail.com', 'Royal Beard Sculpt & Hot Towel', '03:30 PM', '2026-09-02', 'Priya Nair', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(53, 1, 'Tanvi Reddy', '9843742830', 'tanvi.reddy39@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-09-03', 'Priya Nair', 1200, 50, 'Completed', 'Booked via POS & Online Portal'),
	(54, 1, 'Tanvi Bose', '9889133014', 'tanvi.bose77@gmail.com', 'Women''s Layer Cut & Blowdry', '07:15 PM', '2026-09-19', 'Alex Rivera', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(55, 1, 'Tanvi Mehta', '9817318358', 'tanvi.mehta80@gmail.com', 'Hydra-Dew Glow Facial', '12:30 PM', '2026-09-19', 'Marcus Vance', 1652, 60, 'Completed', 'Booked via POS & Online Portal'),
	(56, 1, 'Ishita Iyer', '9816895666', 'ishita.iyer42@gmail.com', 'Express Blowdry & Styling + Signature Haircut & Wash', '07:15 PM', '2026-09-12', 'Alex Rivera', 950, 30, 'Completed', 'Booked via POS & Online Portal'),
	(57, 1, 'Pooja Gupta', '9825898299', 'pooja.gupta81@gmail.com', 'Luxury Organic Hair Spa + Keratin Smooth Treatment', '03:30 PM', '2026-09-27', 'Marcus Vance', 5600, 50, 'Completed', 'Booked via POS & Online Portal'),
	(58, 1, 'Rahul Joshi', '9893955206', 'rahul.joshi37@gmail.com', 'Women''s Layer Cut & Blowdry', '10:00 AM', '2026-09-11', 'Alex Rivera', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(59, 1, 'Nikhil Mukherjee', '9889699989', 'nikhil.mukherjee70@gmail.com', 'Luxury Organic Hair Spa', '06:00 PM', '2026-09-26', 'Priya Nair', 1150, 50, 'Completed', 'Booked via POS & Online Portal'),
	(60, 1, 'Simran Rao', '9883089925', 'simran.rao38@gmail.com', 'Full Balayage & Toning', '02:00 PM', '2026-09-26', 'Alex Rivera', 3776, 120, 'Completed', 'Booked via POS & Online Portal'),
	(61, 1, 'Ananya Mukherjee', '9864023778', 'ananya.mukherjee44@gmail.com', 'Express Blowdry & Styling', '07:15 PM', '2026-09-12', 'Priya Nair', 590, 30, 'Completed', 'Booked via POS & Online Portal'),
	(62, 1, 'Neha Roy', '9840725714', 'neha.roy96@gmail.com', 'Signature Haircut & Wash + Keratin Smooth Treatment', '03:30 PM', '2026-09-03', 'Marcus Vance', 4900, 35, 'Completed', 'Booked via POS & Online Portal'),
	(63, 1, 'Simran Sen', '9875998319', 'simran.sen21@gmail.com', 'Keratin Smooth Treatment', '12:30 PM', '2026-08-31', 'Priya Nair', 4450, 90, 'Completed', 'Booked via POS & Online Portal'),
	(64, 1, 'Sameer Sharma', '9863747791', 'sameer.sharma80@gmail.com', 'Women''s Layer Cut & Blowdry', '07:15 PM', '2026-09-09', 'Priya Nair', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(65, 1, 'Kunal Mehta', '9835176902', 'kunal.mehta76@gmail.com', 'Express Blowdry & Styling', '07:15 PM', '2026-09-05', 'Marcus Vance', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(66, 1, 'Sameer Bhatia', '9875056916', 'sameer.bhatia25@gmail.com', 'Luxury Organic Hair Spa', '12:30 PM', '2026-09-17', 'Marcus Vance', 1200, 50, 'Completed', 'Booked via POS & Online Portal'),
	(67, 1, 'Sneha Bhatia', '9825766039', 'sneha.bhatia92@gmail.com', 'Express Blowdry & Styling + Royal Beard Sculpt & Hot Towel', '02:00 PM', '2026-08-26', 'Priya Nair', 850, 30, 'Completed', 'Booked via POS & Online Portal'),
	(68, 1, 'Tara Menon', '9829413516', 'tara.menon59@gmail.com', 'Hydra-Dew Glow Facial', '02:00 PM', '2026-09-04', 'Alex Rivera', 1450, 60, 'Completed', 'Booked via POS & Online Portal'),
	(69, 1, 'Ananya Aggarwal', '9887835998', 'ananya.aggarwal94@gmail.com', 'Hydra-Dew Glow Facial', '03:30 PM', '2026-09-09', 'Priya Nair', 1400, 60, 'Completed', 'Booked via POS & Online Portal'),
	(70, 1, 'Varun Mukherjee', '9842051937', 'varun.mukherjee83@gmail.com', 'Keratin Smooth Treatment', '04:45 PM', '2026-08-27', 'Alex Rivera', 4450, 90, 'Completed', 'Booked via POS & Online Portal'),
	(71, 1, 'Sanjana Mehta', '9826944487', 'sanjana.mehta74@gmail.com', 'Royal Beard Sculpt & Hot Towel + Keratin Smooth Treatment', '12:30 PM', '2026-09-06', 'Alex Rivera', 5605, 25, 'Completed', 'Booked via POS & Online Portal'),
	(72, 1, 'Aditya Malhotra', '9845570755', 'aditya.malhotra53@gmail.com', 'Keratin Smooth Treatment', '12:30 PM', '2026-09-30', 'Marcus Vance', 4500, 90, 'Confirmed', 'Booked via POS & Online Portal'),
	(73, 1, 'Siddharth Patel', '9819183277', 'siddharth.patel40@gmail.com', 'Full Balayage & Toning', '07:15 PM', '2026-09-06', 'Alex Rivera', 3200, 120, 'Completed', 'Booked via POS & Online Portal'),
	(74, 1, 'Neha Mehta', '9853536830', 'neha.mehta17@gmail.com', 'Royal Beard Sculpt & Hot Towel', '03:30 PM', '2026-09-24', 'Priya Nair', 413, 25, 'Completed', 'Booked via POS & Online Portal'),
	(75, 1, 'Pooja Patel', '9861344226', 'pooja.patel89@gmail.com', 'Express Blowdry & Styling', '12:30 PM', '2026-09-04', 'Marcus Vance', 590, 30, 'Completed', 'Booked via POS & Online Portal'),
	(76, 1, 'Tara Reddy', '9883363160', 'tara.reddy30@gmail.com', 'Royal Beard Sculpt & Hot Towel', '10:00 AM', '2026-09-14', 'Marcus Vance', 413, 25, 'Completed', 'Booked via POS & Online Portal'),
	(77, 1, 'Amit Malhotra', '9824314759', 'amit.malhotra40@gmail.com', 'Royal Beard Sculpt & Hot Towel', '02:00 PM', '2026-09-14', 'Marcus Vance', 413, 25, 'Completed', 'Booked via POS & Online Portal'),
	(78, 1, 'Tanvi Kapoor', '9885957706', 'tanvi.kapoor97@gmail.com', 'Signature Haircut & Wash + Full Balayage & Toning', '06:00 PM', '2026-09-12', 'Marcus Vance', 3550, 35, 'Completed', 'Booked via POS & Online Portal'),
	(79, 1, 'Akash Sharma', '9898473848', 'akash.sharma97@gmail.com', 'Women''s Layer Cut & Blowdry + Royal Beard Sculpt & Hot Towel', '02:00 PM', '2026-09-16', 'Marcus Vance', 1100, 45, 'Completed', 'Booked via POS & Online Portal'),
	(80, 1, 'Pooja Reddy', '9853851498', 'pooja.reddy63@gmail.com', 'Hydra-Dew Glow Facial', '12:30 PM', '2026-09-28', 'Marcus Vance', 1450, 60, 'Completed', 'Booked via POS & Online Portal'),
	(81, 1, 'Ishita Rao', '9872858374', 'ishita.rao19@gmail.com', 'Luxury Organic Hair Spa', '03:30 PM', '2026-09-20', 'Marcus Vance', 1100, 50, 'Completed', 'Booked via POS & Online Portal'),
	(82, 1, 'Akash Menon', '9826587799', 'akash.menon68@gmail.com', 'Full Balayage & Toning', '10:00 AM', '2026-09-07', 'Marcus Vance', 3100, 120, 'Completed', 'Booked via POS & Online Portal'),
	(83, 1, 'Vikram Patel', '9839711402', 'vikram.patel92@gmail.com', 'Express Blowdry & Styling', '10:00 AM', '2026-09-24', 'Marcus Vance', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(84, 1, 'Ananya Malhotra', '9825585427', 'ananya.malhotra22@gmail.com', 'Hydra-Dew Glow Facial', '10:00 AM', '2026-09-23', 'Priya Nair', 1400, 60, 'Completed', 'Booked via POS & Online Portal'),
	(85, 1, 'Kunal Sen', '9823290458', 'kunal.sen72@gmail.com', 'Full Balayage & Toning', '12:30 PM', '2026-08-27', 'Alex Rivera', 3717, 120, 'Completed', 'Booked via POS & Online Portal'),
	(86, 1, 'Gaurav Mehta', '9863437398', 'gaurav.mehta45@gmail.com', 'Women''s Layer Cut & Blowdry', '04:45 PM', '2026-09-15', 'Priya Nair', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(87, 1, 'Manish Aggarwal', '9837542226', 'manish.aggarwal18@gmail.com', 'Luxury Organic Hair Spa + Full Balayage & Toning', '02:00 PM', '2026-09-29', 'Alex Rivera', 4400, 50, 'Confirmed', 'Booked via POS & Online Portal'),
	(88, 1, 'Akash Iyer', '9824754064', 'akash.iyer94@gmail.com', 'Hydra-Dew Glow Facial + Signature Haircut & Wash', '12:30 PM', '2026-09-30', 'Priya Nair', 1950, 60, 'Completed', 'Booked via POS & Online Portal'),
	(89, 1, 'Sneha Bose', '9818530615', 'sneha.bose70@gmail.com', 'Royal Beard Sculpt & Hot Towel', '06:00 PM', '2026-09-14', 'Marcus Vance', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(90, 1, 'Ananya Bhatia', '9896347724', 'ananya.bhatia13@gmail.com', 'Express Blowdry & Styling', '10:00 AM', '2026-08-29', 'Priya Nair', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(91, 1, 'Vikram Patel', '9829909029', 'vikram.patel18@gmail.com', 'Royal Beard Sculpt & Hot Towel', '11:15 AM', '2026-08-30', 'Priya Nair', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(92, 1, 'Rahul Mukherjee', '9825356396', 'rahul.mukherjee93@gmail.com', 'Luxury Organic Hair Spa', '06:00 PM', '2026-09-12', 'Priya Nair', 1100, 50, 'Completed', 'Booked via POS & Online Portal'),
	(93, 1, 'Rahul Chopra', '9867279295', 'rahul.chopra50@gmail.com', 'Royal Beard Sculpt & Hot Towel', '06:00 PM', '2026-09-09', 'Alex Rivera', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(94, 1, 'Simran Rao', '9860015814', 'simran.rao26@gmail.com', 'Royal Beard Sculpt & Hot Towel', '11:15 AM', '2026-09-26', 'Marcus Vance', 413, 25, 'Completed', 'Booked via POS & Online Portal'),
	(95, 1, 'Gaurav Rao', '9887566910', 'gaurav.rao74@gmail.com', 'Express Blowdry & Styling', '03:30 PM', '2026-09-03', 'Alex Rivera', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(96, 1, 'Karan Singhania', '9885291541', 'karan.singhania89@gmail.com', 'Signature Haircut & Wash', '03:30 PM', '2026-08-26', 'Marcus Vance', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(97, 1, 'Ananya Chopra', '9857113566', 'ananya.chopra10@gmail.com', 'Hydra-Dew Glow Facial', '03:30 PM', '2026-09-13', 'Marcus Vance', 1652, 60, 'Completed', 'Booked via POS & Online Portal'),
	(98, 1, 'Amit Singhania', '9870887307', 'amit.singhania53@gmail.com', 'Full Balayage & Toning', '02:00 PM', '2026-09-29', 'Marcus Vance', 3150, 120, 'Confirmed', 'Booked via POS & Online Portal'),
	(99, 1, 'Kavita Sharma', '9820949687', 'kavita.sharma44@gmail.com', 'Keratin Smooth Treatment', '12:30 PM', '2026-09-25', 'Priya Nair', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(100, 1, 'Sneha Reddy', '9889609131', 'sneha.reddy72@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-08-29', 'Alex Rivera', 3200, 120, 'Completed', 'Booked via POS & Online Portal'),
	(101, 1, 'Rhea Verma', '9844295247', 'rhea.verma47@gmail.com', 'Signature Haircut & Wash', '03:30 PM', '2026-09-27', 'Priya Nair', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(102, 1, 'Gaurav Roy', '9863293990', 'gaurav.roy15@gmail.com', 'Express Blowdry & Styling', '02:00 PM', '2026-09-22', 'Alex Rivera', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(103, 1, 'Sameer Rao', '9864362516', 'sameer.rao12@gmail.com', 'Hydra-Dew Glow Facial + Keratin Smooth Treatment', '06:00 PM', '2026-09-03', 'Marcus Vance', 5900, 60, 'Completed', 'Booked via POS & Online Portal'),
	(104, 1, 'Simran Aggarwal', '9863747464', 'simran.aggarwal77@gmail.com', 'Full Balayage & Toning', '02:00 PM', '2026-09-25', 'Marcus Vance', 3717, 120, 'Completed', 'Booked via POS & Online Portal'),
	(105, 1, 'Gaurav Saxena', '9896629889', 'gaurav.saxena28@gmail.com', 'Hydra-Dew Glow Facial', '02:00 PM', '2026-09-26', 'Priya Nair', 1770, 60, 'Completed', 'Booked via POS & Online Portal'),
	(106, 1, 'Tara Aggarwal', '9887774890', 'tara.aggarwal67@gmail.com', 'Royal Beard Sculpt & Hot Towel', '07:15 PM', '2026-09-26', 'Marcus Vance', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(107, 1, 'Tanvi Aggarwal', '9817539294', 'tanvi.aggarwal55@gmail.com', 'Full Balayage & Toning', '03:30 PM', '2026-09-26', 'Priya Nair', 3658, 120, 'Completed', 'Booked via POS & Online Portal'),
	(108, 1, 'Amit Bhatia', '9887890494', 'amit.bhatia80@gmail.com', 'Signature Haircut & Wash + Luxury Organic Hair Spa', '11:15 AM', '2026-09-12', 'Marcus Vance', 1650, 35, 'Completed', 'Booked via POS & Online Portal'),
	(109, 1, 'Rahul Chopra', '9821318464', 'rahul.chopra74@gmail.com', 'Signature Haircut & Wash', '07:15 PM', '2026-08-29', 'Alex Rivera', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(110, 1, 'Sameer Deshmukh', '9864864099', 'sameer.deshmukh53@gmail.com', 'Signature Haircut & Wash', '04:45 PM', '2026-08-28', 'Marcus Vance', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(111, 1, 'Sameer Nair', '9898122539', 'sameer.nair87@gmail.com', 'Royal Beard Sculpt & Hot Towel + Signature Haircut & Wash', '06:00 PM', '2026-09-09', 'Marcus Vance', 800, 25, 'Completed', 'Booked via POS & Online Portal'),
	(112, 1, 'Ananya Menon', '9860557040', 'ananya.menon92@gmail.com', 'Hydra-Dew Glow Facial + Royal Beard Sculpt & Hot Towel', '11:15 AM', '2026-09-11', 'Marcus Vance', 1850, 60, 'Completed', 'Booked via POS & Online Portal'),
	(113, 1, 'Ananya Iyer', '9838748452', 'ananya.iyer53@gmail.com', 'Express Blowdry & Styling + Women''s Layer Cut & Blowdry', '04:45 PM', '2026-08-29', 'Alex Rivera', 1475, 30, 'Completed', 'Booked via POS & Online Portal'),
	(114, 1, 'Manish Patel', '9860562485', 'manish.patel29@gmail.com', 'Hydra-Dew Glow Facial', '04:45 PM', '2026-09-24', 'Marcus Vance', 1652, 60, 'Completed', 'Booked via POS & Online Portal'),
	(115, 1, 'Nikhil Gupta', '9881673763', 'nikhil.gupta40@gmail.com', 'Express Blowdry & Styling', '03:30 PM', '2026-09-15', 'Alex Rivera', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(116, 1, 'Kunal Iyer', '9836802975', 'kunal.iyer87@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-09-02', 'Alex Rivera', 3100, 120, 'Completed', 'Booked via POS & Online Portal'),
	(117, 1, 'Arjun Nair', '9870306604', 'arjun.nair75@gmail.com', 'Keratin Smooth Treatment', '11:15 AM', '2026-09-24', 'Alex Rivera', 4500, 90, 'Completed', 'Booked via POS & Online Portal'),
	(118, 1, 'Nandini Gupta', '9861830338', 'nandini.gupta20@gmail.com', 'Signature Haircut & Wash', '06:00 PM', '2026-09-29', 'Priya Nair', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(119, 1, 'Rajesh Mukherjee', '9828628439', 'rajesh.mukherjee70@gmail.com', 'Signature Haircut & Wash', '03:30 PM', '2026-09-21', 'Alex Rivera', 531, 35, 'Completed', 'Booked via POS & Online Portal'),
	(120, 1, 'Shreya Reddy', '9826354208', 'shreya.reddy16@gmail.com', 'Express Blowdry & Styling', '03:30 PM', '2026-09-21', 'Alex Rivera', 590, 30, 'Completed', 'Booked via POS & Online Portal'),
	(121, 1, 'Meera Reddy', '9867611469', 'meera.reddy10@gmail.com', 'Luxury Organic Hair Spa', '02:00 PM', '2026-08-27', 'Marcus Vance', 1298, 50, 'Completed', 'Booked via POS & Online Portal'),
	(122, 1, 'Amit Malhotra', '9815843091', 'amit.malhotra91@gmail.com', 'Royal Beard Sculpt & Hot Towel', '10:00 AM', '2026-09-25', 'Priya Nair', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(123, 1, 'Ishita Verma', '9815950635', 'ishita.verma55@gmail.com', 'Hydra-Dew Glow Facial', '11:15 AM', '2026-09-26', 'Marcus Vance', 1400, 60, 'Completed', 'Booked via POS & Online Portal'),
	(124, 1, 'Siddharth Reddy', '9837057085', 'siddharth.reddy15@gmail.com', 'Signature Haircut & Wash + Hydra-Dew Glow Facial', '07:15 PM', '2026-09-19', 'Priya Nair', 1850, 35, 'Completed', 'Booked via POS & Online Portal'),
	(125, 1, 'Sameer Saxena', '9816416148', 'sameer.saxena93@gmail.com', 'Women''s Layer Cut & Blowdry', '02:00 PM', '2026-08-31', 'Priya Nair', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(126, 1, 'Sanjana Mukherjee', '9876776459', 'sanjana.mukherjee57@gmail.com', 'Full Balayage & Toning + Keratin Smooth Treatment', '12:30 PM', '2026-09-02', 'Alex Rivera', 8968, 120, 'Completed', 'Booked via POS & Online Portal'),
	(127, 1, 'Pooja Chopra', '9898707076', 'pooja.chopra47@gmail.com', 'Keratin Smooth Treatment', '11:15 AM', '2026-09-19', 'Alex Rivera', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(128, 1, 'Aditya Sharma', '9895565484', 'aditya.sharma61@gmail.com', 'Hydra-Dew Glow Facial', '10:00 AM', '2026-09-08', 'Alex Rivera', 1500, 60, 'Completed', 'Booked via POS & Online Portal'),
	(129, 1, 'Shreya Sen', '9859167775', 'shreya.sen56@gmail.com', 'Signature Haircut & Wash', '11:15 AM', '2026-09-02', 'Marcus Vance', 531, 35, 'Completed', 'Booked via POS & Online Portal'),
	(130, 1, 'Manish Kulkarni', '9859251188', 'manish.kulkarni60@gmail.com', 'Full Balayage & Toning', '11:15 AM', '2026-09-07', 'Alex Rivera', 3776, 120, 'Completed', 'Booked via POS & Online Portal'),
	(131, 1, 'Akash Nair', '9869897763', 'akash.nair37@gmail.com', 'Full Balayage & Toning + Royal Beard Sculpt & Hot Towel', '11:15 AM', '2026-08-30', 'Priya Nair', 4189, 120, 'Completed', 'Booked via POS & Online Portal'),
	(132, 1, 'Pooja Sharma', '9852894344', 'pooja.sharma95@gmail.com', 'Women''s Layer Cut & Blowdry', '07:15 PM', '2026-09-02', 'Marcus Vance', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(133, 1, 'Sneha Joshi', '9828639738', 'sneha.joshi40@gmail.com', 'Signature Haircut & Wash + Hydra-Dew Glow Facial', '02:00 PM', '2026-09-20', 'Marcus Vance', 1900, 35, 'Completed', 'Booked via POS & Online Portal'),
	(134, 1, 'Deepika Mukherjee', '9874245343', 'deepika.mukherjee77@gmail.com', 'Keratin Smooth Treatment', '03:30 PM', '2026-09-22', 'Marcus Vance', 5310, 90, 'Completed', 'Booked via POS & Online Portal'),
	(135, 1, 'Manish Menon', '9895871687', 'manish.menon85@gmail.com', 'Hydra-Dew Glow Facial', '04:45 PM', '2026-09-26', 'Priya Nair', 1500, 60, 'Completed', 'Booked via POS & Online Portal'),
	(136, 1, 'Vikram Mukherjee', '9840262109', 'vikram.mukherjee54@gmail.com', 'Full Balayage & Toning + Keratin Smooth Treatment', '12:30 PM', '2026-09-21', 'Alex Rivera', 9027, 120, 'Completed', 'Booked via POS & Online Portal'),
	(137, 1, 'Pooja Kulkarni', '9896031876', 'pooja.kulkarni31@gmail.com', 'Hydra-Dew Glow Facial', '03:30 PM', '2026-09-13', 'Alex Rivera', 1450, 60, 'Completed', 'Booked via POS & Online Portal'),
	(138, 1, 'Akash Sen', '9838294221', 'akash.sen83@gmail.com', 'Signature Haircut & Wash', '10:00 AM', '2026-09-28', 'Priya Nair', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(139, 1, 'Deepika Reddy', '9870873663', 'deepika.reddy19@gmail.com', 'Hydra-Dew Glow Facial', '02:00 PM', '2026-09-12', 'Priya Nair', 1400, 60, 'Completed', 'Booked via POS & Online Portal'),
	(140, 1, 'Gaurav Deshmukh', '9827551135', 'gaurav.deshmukh57@gmail.com', 'Women''s Layer Cut & Blowdry', '04:45 PM', '2026-09-09', 'Priya Nair', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(141, 1, 'Rahul Mehta', '9848951595', 'rahul.mehta59@gmail.com', 'Keratin Smooth Treatment + Women''s Layer Cut & Blowdry', '12:30 PM', '2026-09-13', 'Alex Rivera', 5200, 90, 'Completed', 'Booked via POS & Online Portal'),
	(142, 1, 'Tara Malhotra', '9851411602', 'tara.malhotra73@gmail.com', 'Keratin Smooth Treatment', '07:15 PM', '2026-09-10', 'Marcus Vance', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(143, 1, 'Sanjana Patel', '9897813295', 'sanjana.patel96@gmail.com', 'Signature Haircut & Wash', '03:30 PM', '2026-09-08', 'Alex Rivera', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(144, 1, 'Deepika Mehta', '9886541906', 'deepika.mehta81@gmail.com', 'Full Balayage & Toning', '10:00 AM', '2026-09-07', 'Alex Rivera', 3100, 120, 'Completed', 'Booked via POS & Online Portal'),
	(145, 1, 'Deepika Saxena', '9855511258', 'deepika.saxena81@gmail.com', 'Hydra-Dew Glow Facial + Women''s Layer Cut & Blowdry', '11:15 AM', '2026-09-13', 'Marcus Vance', 2150, 60, 'Completed', 'Booked via POS & Online Portal'),
	(146, 1, 'Rajesh Kulkarni', '9871335966', 'rajesh.kulkarni29@gmail.com', 'Hydra-Dew Glow Facial', '04:45 PM', '2026-09-28', 'Priya Nair', 1711, 60, 'Completed', 'Booked via POS & Online Portal'),
	(147, 1, 'Ananya Malhotra', '9812232974', 'ananya.malhotra57@gmail.com', 'Women''s Layer Cut & Blowdry', '07:15 PM', '2026-09-11', 'Priya Nair', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(148, 1, 'Kavita Aggarwal', '9874484744', 'kavita.aggarwal31@gmail.com', 'Keratin Smooth Treatment', '02:00 PM', '2026-09-29', 'Alex Rivera', 5310, 90, 'Completed', 'Booked via POS & Online Portal'),
	(149, 1, 'Kunal Verma', '9865426567', 'kunal.verma98@gmail.com', 'Express Blowdry & Styling', '04:45 PM', '2026-09-18', 'Marcus Vance', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(150, 1, 'Rajesh Kulkarni', '9860576565', 'rajesh.kulkarni50@gmail.com', 'Express Blowdry & Styling + Full Balayage & Toning', '04:45 PM', '2026-09-22', 'Priya Nair', 3650, 30, 'Completed', 'Booked via POS & Online Portal'),
	(151, 1, 'Tanvi Menon', '9850063879', 'tanvi.menon38@gmail.com', 'Full Balayage & Toning + Keratin Smooth Treatment', '02:00 PM', '2026-09-14', 'Priya Nair', 7700, 120, 'Completed', 'Booked via POS & Online Portal'),
	(152, 1, 'Sameer Rao', '9886970753', 'sameer.rao96@gmail.com', 'Keratin Smooth Treatment', '03:30 PM', '2026-09-10', 'Priya Nair', 5310, 90, 'Completed', 'Booked via POS & Online Portal'),
	(153, 1, 'Rajesh Joshi', '9837121108', 'rajesh.joshi78@gmail.com', 'Full Balayage & Toning', '03:30 PM', '2026-09-25', 'Alex Rivera', 3200, 120, 'Completed', 'Booked via POS & Online Portal'),
	(154, 1, 'Karan Mehta', '9823448342', 'karan.mehta62@gmail.com', 'Express Blowdry & Styling', '02:00 PM', '2026-09-15', 'Alex Rivera', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(155, 1, 'Rajesh Sen', '9836770527', 'rajesh.sen46@gmail.com', 'Signature Haircut & Wash', '07:15 PM', '2026-09-30', 'Alex Rivera', 450, 35, 'Confirmed', 'Booked via POS & Online Portal'),
	(156, 1, 'Siddharth Deshmukh', '9876489301', 'siddharth.deshmukh33@gmail.com', 'Full Balayage & Toning + Signature Haircut & Wash', '12:30 PM', '2026-09-28', 'Alex Rivera', 3600, 120, 'Completed', 'Booked via POS & Online Portal'),
	(157, 1, 'Manish Kulkarni', '9872816684', 'manish.kulkarni44@gmail.com', 'Women''s Layer Cut & Blowdry', '07:15 PM', '2026-09-09', 'Priya Nair', 885, 45, 'Completed', 'Booked via POS & Online Portal'),
	(158, 1, 'Sameer Aggarwal', '9835925669', 'sameer.aggarwal32@gmail.com', 'Keratin Smooth Treatment', '04:45 PM', '2026-09-14', 'Priya Nair', 5251, 90, 'Completed', 'Booked via POS & Online Portal'),
	(159, 1, 'Vikram Gupta', '9810916723', 'vikram.gupta43@gmail.com', 'Express Blowdry & Styling', '07:15 PM', '2026-09-24', 'Priya Nair', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(160, 1, 'Shreya Mehta', '9899628735', 'shreya.mehta25@gmail.com', 'Hydra-Dew Glow Facial', '04:45 PM', '2026-09-30', 'Priya Nair', 1450, 60, 'Completed', 'Booked via POS & Online Portal'),
	(161, 1, 'Rajesh Verma', '9871066203', 'rajesh.verma87@gmail.com', 'Express Blowdry & Styling', '12:30 PM', '2026-09-07', 'Marcus Vance', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(162, 1, 'Nandini Roy', '9885721444', 'nandini.roy24@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-09-15', 'Marcus Vance', 1416, 50, 'Completed', 'Booked via POS & Online Portal'),
	(163, 1, 'Sanjana Roy', '9878501420', 'sanjana.roy67@gmail.com', 'Express Blowdry & Styling + Women''s Layer Cut & Blowdry', '02:00 PM', '2026-09-02', 'Marcus Vance', 1150, 30, 'Completed', 'Booked via POS & Online Portal'),
	(164, 1, 'Neha Deshmukh', '9844152669', 'neha.deshmukh10@gmail.com', 'Women''s Layer Cut & Blowdry', '03:30 PM', '2026-08-26', 'Alex Rivera', 750, 45, 'Completed', 'Booked via POS & Online Portal'),
	(165, 1, 'Siddharth Reddy', '9864877191', 'siddharth.reddy33@gmail.com', 'Keratin Smooth Treatment + Hydra-Dew Glow Facial', '07:15 PM', '2026-09-26', 'Priya Nair', 5900, 90, 'Completed', 'Booked via POS & Online Portal'),
	(166, 1, 'Gaurav Rao', '9833954324', 'gaurav.rao78@gmail.com', 'Hydra-Dew Glow Facial', '12:30 PM', '2026-09-06', 'Marcus Vance', 1500, 60, 'Completed', 'Booked via POS & Online Portal'),
	(167, 1, 'Amit Gupta', '9843220503', 'amit.gupta68@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-09-11', 'Alex Rivera', 3776, 120, 'Completed', 'Booked via POS & Online Portal'),
	(168, 1, 'Aditya Rao', '9889717834', 'aditya.rao14@gmail.com', 'Signature Haircut & Wash', '02:00 PM', '2026-09-04', 'Alex Rivera', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(169, 1, 'Kavita Verma', '9877631755', 'kavita.verma47@gmail.com', 'Royal Beard Sculpt & Hot Towel', '02:00 PM', '2026-09-02', 'Marcus Vance', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(170, 1, 'Karan Singhania', '9850332555', 'karan.singhania45@gmail.com', 'Hydra-Dew Glow Facial', '12:30 PM', '2026-09-10', 'Marcus Vance', 1400, 60, 'Completed', 'Booked via POS & Online Portal'),
	(171, 1, 'Kunal Singhania', '9830027648', 'kunal.singhania48@gmail.com', 'Express Blowdry & Styling', '04:45 PM', '2026-09-08', 'Alex Rivera', 500, 30, 'Completed', 'Booked via POS & Online Portal'),
	(172, 1, 'Kunal Menon', '9881134297', 'kunal.menon27@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-09-21', 'Alex Rivera', 3150, 120, 'Completed', 'Booked via POS & Online Portal'),
	(173, 1, 'Kavita Nair', '9860622628', 'kavita.nair96@gmail.com', 'Signature Haircut & Wash', '02:00 PM', '2026-09-07', 'Alex Rivera', 531, 35, 'Completed', 'Booked via POS & Online Portal'),
	(174, 1, 'Ishita Reddy', '9812058055', 'ishita.reddy37@gmail.com', 'Women''s Layer Cut & Blowdry + Royal Beard Sculpt & Hot Towel', '02:00 PM', '2026-08-26', 'Priya Nair', 1100, 45, 'Completed', 'Booked via POS & Online Portal'),
	(175, 1, 'Sameer Deshmukh', '9872579077', 'sameer.deshmukh78@gmail.com', 'Full Balayage & Toning', '04:45 PM', '2026-09-17', 'Priya Nair', 3150, 120, 'Completed', 'Booked via POS & Online Portal'),
	(176, 1, 'Vikram Joshi', '9859755172', 'vikram.joshi50@gmail.com', 'Luxury Organic Hair Spa', '07:15 PM', '2026-09-01', 'Marcus Vance', 1416, 50, 'Completed', 'Booked via POS & Online Portal'),
	(177, 1, 'Ishita Gupta', '9860981231', 'ishita.gupta82@gmail.com', 'Express Blowdry & Styling + Full Balayage & Toning', '02:00 PM', '2026-09-04', 'Marcus Vance', 4307, 30, 'Completed', 'Booked via POS & Online Portal'),
	(178, 1, 'Arjun Verma', '9883356206', 'arjun.verma72@gmail.com', 'Signature Haircut & Wash', '04:45 PM', '2026-08-30', 'Marcus Vance', 531, 35, 'Completed', 'Booked via POS & Online Portal'),
	(179, 1, 'Karan Roy', '9830270856', 'karan.roy11@gmail.com', 'Express Blowdry & Styling', '12:30 PM', '2026-09-27', 'Priya Nair', 590, 30, 'Completed', 'Booked via POS & Online Portal'),
	(180, 1, 'Kunal Kapoor', '9812244945', 'kunal.kapoor77@gmail.com', 'Full Balayage & Toning', '10:00 AM', '2026-08-31', 'Alex Rivera', 3100, 120, 'Completed', 'Booked via POS & Online Portal'),
	(181, 1, 'Shreya Joshi', '9893185576', 'shreya.joshi77@gmail.com', 'Royal Beard Sculpt & Hot Towel', '12:30 PM', '2026-09-24', 'Priya Nair', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(182, 1, 'Karan Reddy', '9820820219', 'karan.reddy93@gmail.com', 'Signature Haircut & Wash + Express Blowdry & Styling', '02:00 PM', '2026-09-07', 'Priya Nair', 950, 35, 'Completed', 'Booked via POS & Online Portal'),
	(183, 1, 'Arjun Roy', '9877089857', 'arjun.roy65@gmail.com', 'Royal Beard Sculpt & Hot Towel', '10:00 AM', '2026-08-31', 'Marcus Vance', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(184, 1, 'Rajesh Nair', '9816249441', 'rajesh.nair19@gmail.com', 'Full Balayage & Toning', '02:00 PM', '2026-08-28', 'Marcus Vance', 3776, 120, 'Completed', 'Booked via POS & Online Portal'),
	(185, 1, 'Deepika Roy', '9850168264', 'deepika.roy30@gmail.com', 'Keratin Smooth Treatment', '12:30 PM', '2026-09-29', 'Marcus Vance', 4450, 90, 'Completed', 'Booked via POS & Online Portal'),
	(186, 1, 'Simran Gupta', '9820202996', 'simran.gupta53@gmail.com', 'Keratin Smooth Treatment', '11:15 AM', '2026-09-25', 'Priya Nair', 4500, 90, 'Completed', 'Booked via POS & Online Portal'),
	(187, 1, 'Simran Iyer', '9888634827', 'simran.iyer94@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-08-30', 'Alex Rivera', 3776, 120, 'Completed', 'Booked via POS & Online Portal'),
	(188, 1, 'Vikram Saxena', '9824301022', 'vikram.saxena21@gmail.com', 'Full Balayage & Toning', '06:00 PM', '2026-09-06', 'Priya Nair', 3150, 120, 'Completed', 'Booked via POS & Online Portal'),
	(189, 1, 'Nikhil Menon', '9884455942', 'nikhil.menon75@gmail.com', 'Signature Haircut & Wash', '06:00 PM', '2026-09-22', 'Alex Rivera', 450, 35, 'Completed', 'Booked via POS & Online Portal'),
	(190, 1, 'Kunal Deshmukh', '9821368176', 'kunal.deshmukh81@gmail.com', 'Luxury Organic Hair Spa + Full Balayage & Toning', '03:30 PM', '2026-09-10', 'Marcus Vance', 4400, 50, 'Completed', 'Booked via POS & Online Portal'),
	(191, 1, 'Sanjana Verma', '9818491573', 'sanjana.verma31@gmail.com', 'Keratin Smooth Treatment', '03:30 PM', '2026-09-22', 'Priya Nair', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(192, 1, 'Varun Bhatia', '9824357588', 'varun.bhatia27@gmail.com', 'Keratin Smooth Treatment', '07:15 PM', '2026-09-14', 'Priya Nair', 4400, 90, 'Completed', 'Booked via POS & Online Portal'),
	(193, 1, 'Ananya Chopra', '9890961645', 'ananya.chopra98@gmail.com', 'Royal Beard Sculpt & Hot Towel', '12:30 PM', '2026-09-02', 'Alex Rivera', 350, 25, 'Completed', 'Booked via POS & Online Portal'),
	(194, 1, 'Vikram Deshmukh', '9847621248', 'vikram.deshmukh60@gmail.com', 'Luxury Organic Hair Spa', '02:00 PM', '2026-09-12', 'Marcus Vance', 1200, 50, 'Completed', 'Booked via POS & Online Portal'),
	(195, 1, 'Nikhil Reddy', '9819282319', 'nikhil.reddy62@gmail.com', 'Hydra-Dew Glow Facial', '02:00 PM', '2026-09-29', 'Marcus Vance', 1711, 60, 'Completed', 'Booked via POS & Online Portal'),
	(196, 1, 'Rajesh Aggarwal', '9863795149', 'rajesh.aggarwal78@gmail.com', 'Keratin Smooth Treatment', '07:15 PM', '2026-09-03', 'Marcus Vance', 4500, 90, 'Completed', 'Booked via POS & Online Portal'),
	(197, 1, 'Gaurav Iyer', '9896838849', 'gaurav.iyer88@gmail.com', 'Keratin Smooth Treatment', '02:00 PM', '2026-08-27', 'Priya Nair', 5192, 90, 'Completed', 'Booked via POS & Online Portal'),
	(198, 1, 'Nikhil Saxena', '9862497139', 'nikhil.saxena69@gmail.com', 'Hydra-Dew Glow Facial + Express Blowdry & Styling', '02:00 PM', '2026-09-14', 'Alex Rivera', 2242, 60, 'Completed', 'Booked via POS & Online Portal'),
	(199, 1, 'Gaurav Reddy', '9856045630', 'gaurav.reddy68@gmail.com', 'Express Blowdry & Styling + Hydra-Dew Glow Facial', '12:30 PM', '2026-09-25', 'Priya Nair', 2000, 30, 'Completed', 'Booked via POS & Online Portal'),
	(200, 1, 'Siddharth Mukherjee', '9825446483', 'siddharth.mukherjee12@gmail.com', 'Women''s Layer Cut & Blowdry + Royal Beard Sculpt & Hot Towel', '03:30 PM', '2026-09-02', 'Alex Rivera', 1100, 45, 'Completed', 'Booked via POS & Online Portal');


--
-- Data for Name: bills; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."bills" ("id", "account_id", "client_name", "client_phone", "subtotal", "discount", "tax", "grand_total", "payment_mode", "created_at", "items_json") VALUES
	('INV-2026-1001', 1, 'Shreya Gupta', '9828728463', 750, 0, 0, 750, 'UPI', 1790137479, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1002', 1, 'Varun Mukherjee', '9897226012', 1200, 50, 0, 1150, 'UPI', 1790323779, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1003', 1, 'Meera Joshi', '9855176955', 750, 0, 0, 750, 'Cash', 1789886379, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1004', 1, 'Sneha Deshmukh', '9820576383', 350, 0, 63, 413, 'UPI', 1789359879, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1005', 1, 'Karan Rao', '9861019678', 350, 0, 0, 350, 'UPI', 1790579379, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1006', 1, 'Shreya Iyer', '9872043515', 1200, 50, 0, 1150, 'UPI', 1789277079, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1007', 1, 'Tanvi Roy', '9838317637', 1100, 100, 0, 1000, 'Cash', 1789543479, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1008', 1, 'Shreya Bose', '9885345555', 4500, 100, 0, 4400, 'UPI', 1788246579, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1009', 1, 'Sneha Verma', '9894214382', 7700, 100, 0, 7600, 'Card', 1787992779, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1010', 1, 'Sneha Sharma', '9882070937', 800, 0, 0, 800, 'Card', 1787892879, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}, {"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1011', 1, 'Rahul Sen', '9850056581', 1200, 50, 0, 1150, 'Cash', 1790744079, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1012', 1, 'Sneha Saxena', '9851273847', 750, 0, 0, 750, 'UPI', 1790747679, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1013', 1, 'Arjun Nair', '9880823176', 1200, 0, 0, 1200, 'Card', 1790050179, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1014', 1, 'Sneha Gupta', '9840158366', 1200, 0, 216, 1416, 'Cash', 1788755979, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1015', 1, 'Ishita Roy', '9879008866', 500, 0, 0, 500, 'Cash', 1790500179, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1016', 1, 'Varun Rao', '9823009833', 4500, 100, 0, 4400, 'UPI', 1788156579, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1017', 1, 'Rahul Gupta', '9835714784', 1500, 0, 270, 1770, 'UPI', 1790231079, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1018', 1, 'Kavita Sen', '9882556484', 1950, 100, 0, 1850, 'Card', 1790397579, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1019', 1, 'Amit Nair', '9871070189', 500, 0, 90, 590, 'UPI', 1790489379, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1020', 1, 'Kavita Mehta', '9888406989', 1500, 0, 0, 1500, 'UPI', 1790483079, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1021', 1, 'Shreya Aggarwal', '9889795010', 4500, 50, 0, 4450, 'UPI', 1790402979, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1022', 1, 'Manish Sharma', '9896637649', 750, 0, 0, 750, 'Cash', 1789024179, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1023', 1, 'Akash Verma', '9856843172', 1850, 100, 0, 1750, 'Cash', 1790227479, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}, {"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1024', 1, 'Rahul Verma', '9845496015', 2000, 0, 0, 2000, 'UPI', 1789100679, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}, {"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1025', 1, 'Pooja Sen', '9866851377', 350, 0, 0, 350, 'Card', 1789367979, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1026', 1, 'Rohan Rao', '9820099059', 4950, 0, 0, 4950, 'UPI', 1789879179, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1027', 1, 'Rhea Sharma', '9843491314', 4500, 0, 0, 4500, 'UPI', 1789116879, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1028', 1, 'Divya Bose', '9854585178', 2700, 0, 0, 2700, 'UPI', 1789884579, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Alex Rivera"}, {"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1029', 1, 'Gaurav Reddy', '9840547349', 1200, 50, 207, 1357, 'UPI', 1788163779, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1030', 1, 'Ishita Kapoor', '9825480907', 3200, 0, 0, 3200, 'Card', 1789271679, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1031', 1, 'Amit Aggarwal', '9835511941', 4500, 0, 0, 4500, 'UPI', 1789015179, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1032', 1, 'Ananya Kulkarni', '9851511484', 4500, 50, 0, 4450, 'UPI', 1788926079, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1033', 1, 'Ananya Deshmukh', '9883542887', 1200, 50, 0, 1150, 'Card', 1788493179, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1034', 1, 'Pooja Reddy', '9879182797', 350, 0, 0, 350, 'UPI', 1789616379, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1035', 1, 'Neha Mehta', '9842862209', 750, 0, 0, 750, 'Cash', 1789114179, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1036', 1, 'Shreya Verma', '9898054615', 750, 0, 135, 885, 'Cash', 1789709979, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1037', 1, 'Sneha Bhatia', '9827896471', 350, 0, 0, 350, 'Cash', 1787906379, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1038', 1, 'Arjun Bose', '9873709724', 1200, 50, 0, 1150, 'Cash', 1787978379, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1039', 1, 'Aditya Mukherjee', '9848349783', 350, 0, 63, 413, 'UPI', 1788073779, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1040', 1, 'Rhea Roy', '9865682626', 500, 0, 90, 590, 'Card', 1789529979, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1041', 1, 'Rajesh Kapoor', '9857212267', 7700, 0, 0, 7700, 'Card', 1788672279, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1042', 1, 'Ishita Sharma', '9864266464', 4700, 0, 0, 4700, 'Cash', 1788424779, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1043', 1, 'Manish Bhatia', '9834391257', 350, 0, 0, 350, 'Card', 1790655879, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1044', 1, 'Rajesh Kapoor', '9882399599', 1100, 0, 0, 1100, 'Cash', 1789281579, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1045', 1, 'Neha Patel', '9830452412', 750, 0, 0, 750, 'Card', 1790583879, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1046', 1, 'Arjun Reddy', '9824508768', 3200, 100, 0, 3100, 'Cash', 1789372479, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1047', 1, 'Rahul Mukherjee', '9850477742', 750, 0, 0, 750, 'Card', 1789709079, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1048', 1, 'Aditya Kulkarni', '9896911784', 4500, 0, 0, 4500, 'Card', 1787801979, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1049', 1, 'Tanvi Patel', '9882232344', 3200, 0, 0, 3200, 'UPI', 1788242979, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1050', 1, 'Amit Chopra', '9813852048', 2700, 50, 0, 2650, 'Card', 1789285179, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}, {"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1051', 1, 'Varun Roy', '9842394260', 1200, 100, 0, 1100, 'Card', 1789275279, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1052', 1, 'Karan Deshmukh', '9842655866', 350, 0, 0, 350, 'Card', 1788341079, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1053', 1, 'Tanvi Reddy', '9843742830', 1200, 0, 0, 1200, 'Cash', 1788418479, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1054', 1, 'Tanvi Bose', '9889133014', 750, 0, 135, 885, 'Card', 1789805379, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1055', 1, 'Tanvi Mehta', '9817318358', 1500, 100, 252, 1652, 'UPI', 1789808079, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1056', 1, 'Ishita Iyer', '9816895666', 950, 0, 0, 950, 'UPI', 1789191579, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}, {"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1057', 1, 'Pooja Gupta', '9825898299', 5700, 100, 0, 5600, 'Card', 1790496579, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1058', 1, 'Rahul Joshi', '9893955206', 750, 0, 135, 885, 'Cash', 1789108779, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1059', 1, 'Nikhil Mukherjee', '9889699989', 1200, 50, 0, 1150, 'Card', 1790413779, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1060', 1, 'Simran Rao', '9883089925', 3200, 0, 576, 3776, 'Card', 1790406579, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1061', 1, 'Ananya Mukherjee', '9864023778', 500, 0, 90, 590, 'UPI', 1789202379, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1062', 1, 'Neha Roy', '9840725714', 4950, 50, 0, 4900, 'UPI', 1788411279, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1063', 1, 'Simran Sen', '9875998319', 4500, 50, 0, 4450, 'UPI', 1788158379, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1064', 1, 'Sameer Sharma', '9863747791', 750, 0, 135, 885, 'UPI', 1788925179, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1065', 1, 'Kunal Mehta', '9835176902', 500, 0, 0, 500, 'UPI', 1788582279, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1066', 1, 'Sameer Bhatia', '9875056916', 1200, 0, 0, 1200, 'UPI', 1789620879, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1067', 1, 'Sneha Bhatia', '9825766039', 850, 0, 0, 850, 'Card', 1787733579, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}, {"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1068', 1, 'Tara Menon', '9829413516', 1500, 50, 0, 1450, 'Card', 1788500379, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1069', 1, 'Ananya Aggarwal', '9887835998', 1500, 100, 0, 1400, 'Cash', 1788944079, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1070', 1, 'Varun Mukherjee', '9842051937', 4500, 50, 0, 4450, 'Cash', 1787809179, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1071', 1, 'Sanjana Mehta', '9826944487', 4850, 100, 855, 5605, 'Card', 1788665979, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1072', 1, 'Aditya Malhotra', '9845570755', 4500, 0, 0, 4500, 'Cash', 1790748579, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1073', 1, 'Siddharth Patel', '9819183277', 3200, 0, 0, 3200, 'UPI', 1788666879, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1074', 1, 'Neha Mehta', '9853536830', 350, 0, 63, 413, 'Cash', 1790235579, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1075', 1, 'Pooja Patel', '9861344226', 500, 0, 90, 590, 'Card', 1788509379, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1076', 1, 'Tara Reddy', '9883363160', 350, 0, 63, 413, 'Card', 1789367979, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1077', 1, 'Amit Malhotra', '9824314759', 350, 0, 63, 413, 'Cash', 1789367979, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1078', 1, 'Tanvi Kapoor', '9885957706', 3650, 100, 0, 3550, 'Card', 1789187079, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1079', 1, 'Akash Sharma', '9898473848', 1100, 0, 0, 1100, 'Card', 1789545279, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}, {"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1080', 1, 'Pooja Reddy', '9853851498', 1500, 50, 0, 1450, 'Card', 1790567679, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1081', 1, 'Ishita Rao', '9872858374', 1200, 100, 0, 1100, 'Cash', 1789883679, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1082', 1, 'Akash Menon', '9826587799', 3200, 100, 0, 3100, 'Card', 1788762279, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1083', 1, 'Vikram Patel', '9839711402', 500, 0, 0, 500, 'Card', 1790230179, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1084', 1, 'Ananya Malhotra', '9825585427', 1500, 100, 0, 1400, 'Cash', 1790154579, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1085', 1, 'Kunal Sen', '9823290458', 3200, 50, 567, 3717, 'Card', 1787805579, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1086', 1, 'Gaurav Mehta', '9863437398', 750, 0, 135, 885, 'UPI', 1789462479, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1087', 1, 'Manish Aggarwal', '9837542226', 4400, 0, 0, 4400, 'UPI', 1790666679, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Alex Rivera"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1088', 1, 'Akash Iyer', '9824754064', 1950, 0, 0, 1950, 'UPI', 1790754879, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}, {"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1089', 1, 'Sneha Bose', '9818530615', 350, 0, 0, 350, 'Card', 1789374279, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1090', 1, 'Ananya Bhatia', '9896347724', 500, 0, 0, 500, 'UPI', 1787980179, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1091', 1, 'Vikram Patel', '9829909029', 350, 0, 0, 350, 'Cash', 1788079179, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1092', 1, 'Rahul Mukherjee', '9825356396', 1200, 100, 0, 1100, 'Card', 1789187979, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1093', 1, 'Rahul Chopra', '9867279295', 350, 0, 0, 350, 'Card', 1788932379, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1094', 1, 'Simran Rao', '9860015814', 350, 0, 63, 413, 'Card', 1790414679, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1095', 1, 'Gaurav Rao', '9887566910', 500, 0, 0, 500, 'Card', 1788420279, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1096', 1, 'Karan Singhania', '9885291541', 450, 0, 0, 450, 'Cash', 1787734479, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1097', 1, 'Ananya Chopra', '9857113566', 1500, 100, 252, 1652, 'Cash', 1789287879, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1098', 1, 'Amit Singhania', '9870887307', 3200, 50, 0, 3150, 'Cash', 1790655879, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1099', 1, 'Kavita Sharma', '9820949687', 4500, 100, 0, 4400, 'UPI', 1790324679, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1100', 1, 'Sneha Reddy', '9889609131', 3200, 0, 0, 3200, 'Cash', 1787988279, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1101', 1, 'Rhea Verma', '9844295247', 450, 0, 0, 450, 'UPI', 1790497479, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1102', 1, 'Gaurav Roy', '9863293990', 500, 0, 0, 500, 'Cash', 1790051979, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1103', 1, 'Sameer Rao', '9864362516', 6000, 100, 0, 5900, 'Card', 1788406779, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1104', 1, 'Simran Aggarwal', '9863747464', 3200, 50, 567, 3717, 'UPI', 1790325579, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1105', 1, 'Gaurav Saxena', '9896629889', 1500, 0, 270, 1770, 'UPI', 1790400279, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1106', 1, 'Tara Aggarwal', '9887774890', 350, 0, 0, 350, 'Card', 1790395779, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1107', 1, 'Tanvi Aggarwal', '9817539294', 3200, 100, 558, 3658, 'Card', 1790401179, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1108', 1, 'Amit Bhatia', '9887890494', 1650, 0, 0, 1650, 'Card', 1789187079, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}, {"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1109', 1, 'Rahul Chopra', '9821318464', 450, 0, 0, 450, 'Card', 1787994579, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1110', 1, 'Sameer Deshmukh', '9864864099', 450, 0, 0, 450, 'UPI', 1787900979, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1111', 1, 'Sameer Nair', '9898122539', 800, 0, 0, 800, 'Card', 1788931479, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}, {"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1112', 1, 'Ananya Menon', '9860557040', 1850, 0, 0, 1850, 'Card', 1789112379, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1113', 1, 'Ananya Iyer', '9838748452', 1250, 0, 225, 1475, 'Card', 1787993679, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1114', 1, 'Manish Patel', '9860562485', 1500, 100, 252, 1652, 'Card', 1790223879, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1115', 1, 'Nikhil Gupta', '9881673763', 500, 0, 0, 500, 'Cash', 1789447179, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1116', 1, 'Kunal Iyer', '9836802975', 3200, 100, 0, 3100, 'Cash', 1788331179, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1117', 1, 'Arjun Nair', '9870306604', 4500, 0, 0, 4500, 'Card', 1790234679, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1118', 1, 'Nandini Gupta', '9861830338', 450, 0, 0, 450, 'Cash', 1790671179, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1119', 1, 'Rajesh Mukherjee', '9828628439', 450, 0, 81, 531, 'UPI', 1789981779, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1120', 1, 'Shreya Reddy', '9826354208', 500, 0, 90, 590, 'Card', 1789979979, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1121', 1, 'Meera Reddy', '9867611469', 1200, 100, 198, 1298, 'Cash', 1787804679, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1122', 1, 'Amit Malhotra', '9815843091', 350, 0, 0, 350, 'Card', 1790326479, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1123', 1, 'Ishita Verma', '9815950635', 1500, 100, 0, 1400, 'Card', 1790409279, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1124', 1, 'Siddharth Reddy', '9837057085', 1950, 100, 0, 1850, 'Cash', 1789808979, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}, {"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1125', 1, 'Sameer Saxena', '9816416148', 750, 0, 0, 750, 'Card', 1788166479, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1126', 1, 'Sanjana Mukherjee', '9876776459', 7700, 100, 1368, 8968, 'Cash', 1788331179, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1127', 1, 'Pooja Chopra', '9898707076', 4500, 100, 0, 4400, 'UPI', 1789800879, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1128', 1, 'Aditya Sharma', '9895565484', 1500, 0, 0, 1500, 'Cash', 1788849579, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1129', 1, 'Shreya Sen', '9859167775', 450, 0, 81, 531, 'Card', 1788337479, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1130', 1, 'Manish Kulkarni', '9859251188', 3200, 0, 576, 3776, 'UPI', 1788760479, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1131', 1, 'Akash Nair', '9869897763', 3550, 0, 639, 4189, 'UPI', 1788064779, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}, {"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1132', 1, 'Pooja Sharma', '9852894344', 750, 0, 0, 750, 'Card', 1788322179, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1133', 1, 'Sneha Joshi', '9828639738', 1950, 50, 0, 1900, 'Cash', 1789888179, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}, {"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1134', 1, 'Deepika Mukherjee', '9874245343', 4500, 0, 810, 5310, 'Card', 1790069079, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1135', 1, 'Manish Menon', '9895871687', 1500, 0, 0, 1500, 'Cash', 1790401179, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1136', 1, 'Vikram Mukherjee', '9840262109', 7700, 50, 1377, 9027, 'Cash', 1789977279, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1137', 1, 'Pooja Kulkarni', '9896031876', 1500, 50, 0, 1450, 'Cash', 1789272579, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1138', 1, 'Akash Sen', '9838294221', 450, 0, 0, 450, 'Cash', 1790587479, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1139', 1, 'Deepika Reddy', '9870873663', 1500, 100, 0, 1400, 'UPI', 1789192479, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1140', 1, 'Gaurav Deshmukh', '9827551135', 750, 0, 135, 885, 'UPI', 1788937779, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1141', 1, 'Rahul Mehta', '9848951595', 5250, 50, 0, 5200, 'Cash', 1789285179, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1142', 1, 'Tara Malhotra', '9851411602', 4500, 100, 0, 4400, 'UPI', 1789027779, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1143', 1, 'Sanjana Patel', '9897813295', 450, 0, 0, 450, 'Card', 1788859479, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1144', 1, 'Deepika Mehta', '9886541906', 3200, 100, 0, 3100, 'Cash', 1788763179, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1145', 1, 'Deepika Saxena', '9855511258', 2250, 100, 0, 2150, 'UPI', 1789287879, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1146', 1, 'Rajesh Kulkarni', '9871335966', 1500, 50, 261, 1711, 'Cash', 1790568579, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1147', 1, 'Ananya Malhotra', '9812232974', 750, 0, 0, 750, 'Cash', 1789102479, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1148', 1, 'Kavita Aggarwal', '9874484744', 4500, 0, 810, 5310, 'Cash', 1790663979, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1149', 1, 'Kunal Verma', '9865426567', 500, 0, 0, 500, 'Cash', 1789712679, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1150', 1, 'Rajesh Kulkarni', '9860576565', 3700, 50, 0, 3650, 'Cash', 1790053779, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1151', 1, 'Tanvi Menon', '9850063879', 7700, 0, 0, 7700, 'Card', 1789371579, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}, {"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1152', 1, 'Sameer Rao', '9886970753', 4500, 0, 810, 5310, 'Card', 1789022379, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1153', 1, 'Rajesh Joshi', '9837121108', 3200, 0, 0, 3200, 'Cash', 1790315679, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1154', 1, 'Karan Mehta', '9823448342', 500, 0, 0, 500, 'UPI', 1789463379, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1155', 1, 'Rajesh Sen', '9836770527', 450, 0, 0, 450, 'UPI', 1790748579, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1156', 1, 'Siddharth Deshmukh', '9876489301', 3650, 50, 0, 3600, 'UPI', 1790575779, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}, {"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1157', 1, 'Manish Kulkarni', '9872816684', 750, 0, 135, 885, 'Card', 1788933279, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1158', 1, 'Sameer Aggarwal', '9835925669', 4500, 50, 801, 5251, 'Cash', 1789376979, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1159', 1, 'Vikram Gupta', '9810916723', 500, 0, 0, 500, 'Card', 1790237379, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1160', 1, 'Shreya Mehta', '9899628735', 1500, 50, 0, 1450, 'Cash', 1790740479, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1161', 1, 'Rajesh Verma', '9871066203', 500, 0, 0, 500, 'UPI', 1788768579, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1162', 1, 'Nandini Roy', '9885721444', 1200, 0, 216, 1416, 'Cash', 1789449879, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1163', 1, 'Sanjana Roy', '9878501420', 1250, 100, 0, 1150, 'UPI', 1788323079, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1164', 1, 'Neha Deshmukh', '9844152669', 750, 0, 0, 750, 'Cash', 1787715579, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1165', 1, 'Siddharth Reddy', '9864877191', 6000, 100, 0, 5900, 'Card', 1790414679, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}, {"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1166', 1, 'Gaurav Rao', '9833954324', 1500, 0, 0, 1500, 'UPI', 1788668679, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1167', 1, 'Amit Gupta', '9843220503', 3200, 0, 576, 3776, 'Cash', 1789097979, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1168', 1, 'Aditya Rao', '9889717834', 450, 0, 0, 450, 'Card', 1788510279, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1169', 1, 'Kavita Verma', '9877631755', 350, 0, 0, 350, 'Cash', 1788325779, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1170', 1, 'Karan Singhania', '9850332555', 1500, 100, 0, 1400, 'UPI', 1789024179, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1171', 1, 'Kunal Singhania', '9830027648', 500, 0, 0, 500, 'Card', 1788842379, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1172', 1, 'Kunal Menon', '9881134297', 3200, 50, 0, 3150, 'Card', 1789979979, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1173', 1, 'Kavita Nair', '9860622628', 450, 0, 81, 531, 'Cash', 1788758679, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1174', 1, 'Ishita Reddy', '9812058055', 1100, 0, 0, 1100, 'Cash', 1787724579, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Priya Nair"}, {"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1175', 1, 'Sameer Deshmukh', '9872579077', 3200, 50, 0, 3150, 'Card', 1789630779, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1176', 1, 'Vikram Joshi', '9859755172', 1200, 0, 216, 1416, 'Cash', 1788236679, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1177', 1, 'Ishita Gupta', '9860981231', 3700, 50, 657, 4307, 'Card', 1788508479, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Marcus Vance"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1178', 1, 'Arjun Verma', '9883356206', 450, 0, 81, 531, 'UPI', 1788075579, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1179', 1, 'Karan Roy', '9830270856', 500, 0, 90, 590, 'Cash', 1790490279, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1180', 1, 'Kunal Kapoor', '9812244945', 3200, 100, 0, 3100, 'UPI', 1788165579, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1181', 1, 'Shreya Joshi', '9893185576', 350, 0, 0, 350, 'UPI', 1790227479, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1182', 1, 'Karan Reddy', '9820820219', 950, 0, 0, 950, 'Cash', 1788759579, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Priya Nair"}, {"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1183', 1, 'Arjun Roy', '9877089857', 350, 0, 0, 350, 'UPI', 1788150279, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1184', 1, 'Rajesh Nair', '9816249441', 3200, 0, 576, 3776, 'Card', 1787905479, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1185', 1, 'Deepika Roy', '9850168264', 4500, 50, 0, 4450, 'Cash', 1790658579, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1186', 1, 'Simran Gupta', '9820202996', 4500, 0, 0, 4500, 'Card', 1790326479, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1187', 1, 'Simran Iyer', '9888634827', 3200, 0, 576, 3776, 'UPI', 1788073779, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1188', 1, 'Vikram Saxena', '9824301022', 3200, 50, 0, 3150, 'UPI', 1788667779, '[{"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1189', 1, 'Nikhil Menon', '9884455942', 450, 0, 0, 450, 'UPI', 1790065479, '[{"name": "Signature Haircut & Wash", "category": "Haircuts", "price": 450, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1190', 1, 'Kunal Deshmukh', '9821368176', 4400, 0, 0, 4400, 'UPI', 1789029579, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}, {"name": "Full Balayage & Toning", "category": "Hair Color", "price": 3200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1191', 1, 'Sanjana Verma', '9818491573', 4500, 100, 0, 4400, 'Card', 1790060079, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1192', 1, 'Varun Bhatia', '9824357588', 4500, 100, 0, 4400, 'Card', 1789358979, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1193', 1, 'Ananya Chopra', '9890961645', 350, 0, 0, 350, 'Card', 1788328479, '[{"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1194', 1, 'Vikram Deshmukh', '9847621248', 1200, 0, 0, 1200, 'Cash', 1789187979, '[{"name": "Luxury Organic Hair Spa", "category": "Treatments", "price": 1200, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1195', 1, 'Nikhil Reddy', '9819282319', 1500, 50, 261, 1711, 'Cash', 1790653179, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1196', 1, 'Rajesh Aggarwal', '9863795149', 4500, 0, 0, 4500, 'Card', 1788424779, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Marcus Vance"}]'),
	('INV-2026-1197', 1, 'Gaurav Iyer', '9896838849', 4500, 100, 792, 5192, 'UPI', 1787822679, '[{"name": "Keratin Smooth Treatment", "category": "Treatments", "price": 4500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1198', 1, 'Nikhil Saxena', '9862497139', 2000, 100, 342, 2242, 'Card', 1789362579, '[{"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Alex Rivera"}, {"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Alex Rivera"}]'),
	('INV-2026-1199', 1, 'Gaurav Reddy', '9856045630', 2000, 0, 0, 2000, 'Cash', 1790310279, '[{"name": "Express Blowdry & Styling", "category": "Styling", "price": 500, "qty": 1, "staff": "Priya Nair"}, {"name": "Hydra-Dew Glow Facial", "category": "Spa & Facial", "price": 1500, "qty": 1, "staff": "Priya Nair"}]'),
	('INV-2026-1200', 1, 'Siddharth Mukherjee', '9825446483', 1100, 0, 0, 1100, 'Cash', 1788339279, '[{"name": "Women''s Layer Cut & Blowdry", "category": "Haircuts", "price": 750, "qty": 1, "staff": "Alex Rivera"}, {"name": "Royal Beard Sculpt & Hot Towel", "category": "Bridal & Grooming", "price": 350, "qty": 1, "staff": "Alex Rivera"}]');


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."categories" ("id", "account_id", "name", "created_at") VALUES
	(1, 1, 'Haircuts', 1790760279),
	(2, 1, 'Spa & Facial', 1790760279),
	(3, 1, 'Hair Color', 1790760279),
	(4, 1, 'Styling', 1790760279),
	(5, 1, 'Treatments', 1790760279),
	(6, 1, 'Bridal & Grooming', 1790760279);


--
-- Data for Name: customers; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."customers" ("id", "account_id", "name", "phone", "email", "notes", "created_at") VALUES
	(1, 1, 'Ananya Sharma', '9876543210', 'ananya@gmail.com', 'Prefers weekend slots', 1790760279),
	(2, 1, 'Vikram Malhotra', '9812345678', 'vikram@gmail.com', 'Regular client', 1790760279);


--
-- Data for Name: deletion_requests; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- Data for Name: pendingorders; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- Data for Name: salon_settings; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."salon_settings" ("id", "salon_id", "payment_methods", "created_at", "updated_at") VALUES
	(1, 1, '{"upi": "aura.salon@okaxis", "card_terminal": "Razorpay Smart POS"}', 1790760279, 1790760279);


--
-- Data for Name: services; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."services" ("id", "account_id", "name", "category", "duration", "price", "description", "gender", "staff", "active", "created_at") VALUES
	(1, 1, 'Signature Haircut & Wash', 'Haircuts', 35, 450, 'Includes shampoo, customized hair wash, and blow dry finish.', 'Any', 'Alex Rivera', 1, 1790760279),
	(2, 1, 'Women''s Layer Cut & Blowdry', 'Haircuts', 45, 750, 'Consultation, texture layering, and heat styling.', 'Female', 'Alex Rivera', 1, 1790760279),
	(3, 1, 'Hydra-Dew Glow Facial', 'Spa & Facial', 60, 1500, 'Deep pore ultrasonic cleanse & hydration infusion.', 'Any', 'Priya Nair', 1, 1790760279),
	(4, 1, 'Luxury Organic Hair Spa', 'Treatments', 50, 1200, 'Scalp therapy, argan oil steam wrap & relaxing massage.', 'Any', 'Priya Nair', 1, 1790760279),
	(5, 1, 'Full Balayage & Toning', 'Hair Color', 120, 3200, 'Artisan hair painting with gloss and bond repair.', 'Female', 'Priya Nair', 1, 1790760279),
	(6, 1, 'Royal Beard Sculpt & Hot Towel', 'Bridal & Grooming', 25, 350, 'Precision beard shaping with essential oils & hot towel steam.', 'Male', 'Marcus Vance', 1, 1790760279),
	(7, 1, 'Keratin Smooth Treatment', 'Treatments', 90, 4500, 'Formaldehyde-free protein smoothing with intense shine.', 'Any', 'Alex Rivera', 1, 1790760279),
	(8, 1, 'Express Blowdry & Styling', 'Styling', 30, 500, 'Volume blowdry with heat protectant and styling spray.', 'Any', 'Priya Nair', 1, 1790760279);


--
-- Data for Name: staff; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."staff" ("id", "account_id", "name", "role", "phone", "gender", "email", "total_revenue", "services_done", "created_on") VALUES
	(1, 1, 'Alex Rivera', 'Senior Stylist', '9811023456', 'Male', 'alex@aurasalon.in', 145160, 77, 1790760279),
	(2, 1, 'Priya Nair', 'Master Colorist', '9822034567', 'Female', 'priya@aurasalon.in', 132916, 79, 1790760279),
	(3, 1, 'Marcus Vance', 'Grooming Specialist', '9833045678', 'Male', 'marcus@aurasalon.in', 148640, 89, 1790760279);


--
-- Data for Name: subscriptions; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- Name: accounts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."accounts_id_seq"', 1, false);


--
-- Name: appointments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."appointments_id_seq"', 200, true);


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."categories_id_seq"', 6, true);


--
-- Name: customers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."customers_id_seq"', 2, true);


--
-- Name: deletion_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."deletion_requests_id_seq"', 1, false);


--
-- Name: salon_settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."salon_settings_id_seq"', 1, true);


--
-- Name: salons_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."salons_id_seq"', 1, false);


--
-- Name: services_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."services_id_seq"', 8, true);


--
-- Name: staff_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."staff_id_seq"', 3, true);


--
-- PostgreSQL database dump complete
--

-- \unrestrict gJJJEvj3K7WcK3Em282RO3xblxJZXRoXgQNwrhNdSxxWn6e6YF55aBcmJQ0Tduv

RESET ALL;
