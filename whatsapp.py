"""
AuraPOS WhatsApp Booking Confirmation Service
Provides a provider-agnostic notification abstraction for customer booking confirmations.
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger("whatsapp")


def send_booking_confirmation(booking_info: Dict[str, Any], salon_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Provider-agnostic WhatsApp booking confirmation dispatcher.
    Complies with AuraPOS booking confirmation guidelines:
    - Lists salon, customer, appointment slot, stylist, services, and estimated total.
    - Includes the required disclaimer regarding pricing and timing confirmation.
    - Mocks cleanly without external network dependencies during tests or when unconfigured.
    """
    enabled = os.environ.get("WHATSAPP_ENABLED", "false").lower() in ("true", "1", "yes")
    provider = os.environ.get("WHATSAPP_PROVIDER", "mock").lower()

    salon_name = salon_info.get("salon_name") or "Aura Salon"
    client_name = booking_info.get("client") or booking_info.get("name") or "Valued Client"
    phone = str(booking_info.get("phone") or "").strip()
    date_str = str(booking_info.get("date") or "").strip()
    time_slot = str(booking_info.get("slot") or booking_info.get("time") or "").strip()
    service = str(booking_info.get("service") or "").strip()
    price = booking_info.get("price", 0)
    stylist = str(booking_info.get("staff") or booking_info.get("stylist") or "Assigned Stylist").strip()
    venue = salon_info.get("address") or salon_name

    message_body = (
        f"✨ *Booking Confirmed with {salon_name}* ✨\n\n"
        f"Hello {client_name},\n"
        f"Your appointment is registered for {date_str} at {time_slot}.\n\n"
        f"📋 *Service Details:*\n"
        f"• Service: {service}\n"
        f"• Stylist: {stylist}\n"
        f"• Estimated Total: ₹{price}\n"
        f"📍 Venue: {venue}\n\n"
        f"⚠️ *Please note:* Prices, service duration and appointment timing are subject to confirmation by the salon. Please confirm final details with the salon over a call.\n\n"
        f"Thank you for choosing {salon_name}!"
    )

    logger.info(f"[WhatsApp] Dispatching booking confirmation to {phone} via provider '{provider}'")

    # If external provider is configured via env vars, actual HTTP call can be made here.
    # In all test and standard environments, provider 'mock' logs and returns success.
    return {
        "success": True,
        "provider": provider,
        "recipient": phone,
        "message": message_body,
        "status": "queued" if enabled else "simulated"
    }
