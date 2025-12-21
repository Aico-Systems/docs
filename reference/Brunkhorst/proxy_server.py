#!/usr/bin/env python3
"""
Zeitmechanik Booking Proxy Server - OPTIMIZED V3.1
Converts SOAP/XML API to REST/JSON endpoints

IMPROVEMENTS:
- Consistent response format across all endpoints
- Better error handling with specific error codes
- Enhanced logging for debugging
- Input validation
- Proper null handling
- VAPI-optimized JSON responses
- VAPI tool call format support (auto-detects and handles VAPI requests)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
import json

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://www.zeitmechanik.net/zm3/web/app.php/zbooking2/v1_0"
TOKEN = "460912BGAfMTF"

# Session storage for appointment_ids (keyed by call ID or session)
# This is a workaround for GPT-4's inability to preserve context reliably
ACTIVE_RESERVATIONS = {}

# Service mapping
SERVICES = {
    '2281101': {'id': '2281101', 'name': 'Abgasuntersuchung Benzin', 'category': 'inspection'},
    '2281111': {'id': '2281111', 'name': 'Abgasuntersuchung Diesel', 'category': 'inspection'},
    '2430982': {'id': '2430982', 'name': 'Aufbereitung', 'category': 'service'},
    '2281371': {'id': '2281371', 'name': 'Frühjahrscheck', 'category': 'inspection'},
    '2281131': {'id': '2281131', 'name': 'Hauptuntersuchung', 'category': 'inspection'},
    '2281121': {'id': '2281121', 'name': 'HU Vorkontrolle', 'category': 'inspection'},
    '2281401': {'id': '2281401', 'name': 'Lichttest', 'category': 'inspection'},
    '2281421': {'id': '2281421', 'name': 'Ölwechsel mit Filter', 'category': 'maintenance'},
    '2430983': {'id': '2430983', 'name': 'Räderwechsel', 'category': 'service'},
    '2281381': {'id': '2281381', 'name': 'Urlaubscheck', 'category': 'inspection'},
    '2281341': {'id': '2281341', 'name': 'Wartung Standart', 'category': 'maintenance'},
    '2281391': {'id': '2281391', 'name': 'Wintercheck', 'category': 'inspection'},
}

# HTTP headers for SOAP requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://www.zeitmechanik.net',
    'Referer': f'https://www.zeitmechanik.net/zm3/web/app.php/zbooking2/web-app/v1_0?token={TOKEN}',
    'Connection': 'keep-alive',
}


def extract_vapi_params() -> Optional[Dict]:
    """
    Extract parameters from VAPI request format.
    
    VAPI sends requests in this format:
    {
        "message": {
            "type": "tool-calls",
            "toolCallList": [{
                "id": "toolu_xxx",
                "name": "functionName",
                "arguments": { ... }
            }],
            ...
        }
    }
    
    Returns the arguments dict if VAPI format detected, otherwise returns the request body as-is.
    Also stores toolCallId in g for response formatting.
    """
    from flask import g
    
    body = request.get_json()
    
    if not body:
        logger.warning("No request body received")
        return None
    
    # Log the raw body for debugging
    logger.info(f"Raw request body: {json.dumps(body)[:500]}")
    logger.info(f"Full message keys: {list(body.get('message', {}).keys())}")
    logger.info(f"Top-level body keys: {list(body.keys())}")
    
    # Check if this is a VAPI request
    message = body.get('message', {})
    if message.get('type') == 'tool-calls':
        tool_call_list = message.get('toolCallList', [])
        logger.info(f"Tool call list: {tool_call_list}")
        if tool_call_list and len(tool_call_list) > 0:
            tool_call = tool_call_list[0]
            logger.info(f"Tool call object: {tool_call}")
            g.is_vapi_request = True
            g.vapi_tool_call_id = tool_call.get('id', 'unknown')
            
            # Extract call_id for session tracking
            call_data = message.get('call', {})
            g.call_id = call_data.get('id', 'unknown_call')
            logger.info(f"Extracted call_id: {g.call_id}")
            
            # VAPI nests arguments inside 'function' object
            function = tool_call.get('function', {})
            arguments = function.get('arguments', {})
            function_name = function.get('name', 'unknown')
            
            logger.info(f"VAPI request detected: {function_name} with args: {arguments}")
            return arguments
    
    # Not a VAPI request, return body as-is
    g.is_vapi_request = False
    logger.info(f"Not a VAPI request, returning body as-is")
    return body


def vapi_response(data: Dict, status: int = 200) -> Tuple:
    """
    Format response for VAPI.
    
    VAPI expects:
    {
        "results": [{
            "toolCallId": "toolu_xxx",
            "result": { ... }
        }]
    }
    
    For non-VAPI requests, returns standard response.
    """
    from flask import g
    
    if getattr(g, 'is_vapi_request', False) and hasattr(g, 'vapi_tool_call_id'):
        # Format for VAPI
        vapi_result = {
            "results": [{
                "toolCallId": g.vapi_tool_call_id,
                "result": data
            }]
        }
        return jsonify(vapi_result), status
    else:
        # Standard response
        return jsonify(data), status


def success_response(data: Dict, status: int = 200) -> Tuple:
    """Standard success response with VAPI support"""
    response = {'success': True}
    response.update(data)
    return vapi_response(response, status)


def error_response(message: str, error_code: str = 'ERROR', details: Optional[Dict] = None, status: int = 400) -> Tuple:
    """Standard error response with VAPI support"""
    response = {
        'success': False,
        'error': message,
        'error_code': error_code
    }
    if details:
        response['details'] = details
    logger.error(f"Error {error_code}: {message} - Details: {details}")
    return vapi_response(response, status)


def post_soap_request(xml_body: str) -> str:
    """Send SOAP request to Zeitmechanik API"""
    try:
        logger.debug(f"SOAP Request: {xml_body[:500]}...")
        response = requests.post(BASE_URL, data=xml_body, headers=HEADERS, timeout=30)
        logger.debug(f"SOAP Response Status: {response.status_code}")
        logger.debug(f"SOAP Response: {response.text[:1000]}...")
        response.raise_for_status()
        return response.text
    except requests.Timeout:
        logger.error("SOAP request timeout")
        raise Exception("Connection timeout to booking system")
    except requests.RequestException as e:
        logger.error(f"SOAP request failed: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response text: {e.response.text[:500]}")
        raise Exception(f"Booking system unavailable: {str(e)}")



def parse_soap_fault(xml_response: str) -> Optional[Dict]:
    """Check for SOAP faults and return error if present"""
    try:
        root = ET.fromstring(xml_response)
        fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
        if fault is not None:
            faultcode = fault.find('.//faultcode')
            faultstring = fault.find('.//faultstring')
            return {
                'error': True,
                'code': faultcode.text if faultcode is not None else 'SOAP_FAULT',
                'message': faultstring.text if faultstring is not None else 'Unknown SOAP error'
            }
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        return {'error': True, 'code': 'XML_PARSE_ERROR', 'message': f'Invalid XML response: {str(e)}'}
    return None


def validate_service_ids(service_ids: List[str]) -> Tuple[bool, Optional[str]]:
    """Validate service IDs"""
    if not service_ids or not isinstance(service_ids, list):
        return False, "service_ids must be a non-empty array"
    
    invalid = [sid for sid in service_ids if sid not in SERVICES]
    if invalid:
        return False, f"Invalid service IDs: {', '.join(invalid)}"
    
    return True, None


@app.route('/api/services', methods=['GET', 'POST'])
def get_services():
    """Get list of all available services"""
    try:
        services_list = [
            {
                'id': service_id,
                'name': info['name'],
                'category': info['category']
            }
            for service_id, info in SERVICES.items()
        ]
        return success_response({
            'services': services_list,
            'count': len(services_list)
        })
    except Exception as e:
        return error_response(str(e), 'SERVICES_ERROR', status=500)


@app.route('/api/services/<service_id>', methods=['GET'])
def get_service(service_id: str):
    """Get details for a specific service"""
    if service_id not in SERVICES:
        return error_response(
            f'Service ID {service_id} not found',
            'SERVICE_NOT_FOUND',
            {'available_ids': list(SERVICES.keys())},
            404
        )
    
    return success_response({'service': SERVICES[service_id]})


@app.route('/api/availability/days', methods=['GET', 'POST'])
def get_available_days():
    """
    Get available days for booking
    
    POST JSON body (recommended):
    {
        "service_ids": ["2430983"]
    }
    
    GET Query params:
    ?service_ids=2430983 or ?service_ids=2430983,2281101
    """
    # Parse input
    data = {}  # Initialize data for POST method
    if request.method == 'POST':
        data = extract_vapi_params() or {}
        logger.info(f"POST data received: {data}")
        
        # Accept both service_id (string) and service_ids (array)
        service_ids_param = data.get('service_ids') or data.get('service_id')
        logger.info(f"service_ids_param extracted: {service_ids_param}")
        
        if isinstance(service_ids_param, list):
            service_ids = service_ids_param
        elif isinstance(service_ids_param, str):
            service_ids = [service_ids_param.strip()] if service_ids_param.strip() else None
        else:
            service_ids = None
    else:
        service_ids_param = request.args.get('service_ids')
        if service_ids_param:
            service_ids = [sid.strip() for sid in service_ids_param.split(',') if sid.strip()]
        else:
            service_ids = None
    
    logger.info(f"Final service_ids: {service_ids}")
    
    # Validate input
    if not service_ids:
        return error_response(
            'service_ids parameter is required',
            'MISSING_PARAMETER',
            {'required': 'service_ids', 'format': 'array of strings', 'example': ['2430983']}
        )
    
    valid, error_msg = validate_service_ids(service_ids)
    if not valid:
        return error_response(
            error_msg,
            'INVALID_SERVICE_IDS',
            {'valid_ids': list(SERVICES.keys())}
        )
    
    # Build SOAP request
    work_ids_xml = ''.join([f'<workId>{sid}</workId>' for sid in service_ids])
    vip = data.get('vip', '') if request.method == 'POST' else request.args.get('vip', '')
    
    soap_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:zbo="http://zbooking2.zeitmechanik.net/">
    <soapenv:Header/>
    <soapenv:Body>
        <zbo:searchAvailableDays>
            <token>{TOKEN}</token>
            <workIds>{work_ids_xml}</workIds>
            <existingReservationId></existingReservationId>
            <vip>{vip}</vip>
        </zbo:searchAvailableDays>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    try:
        response_xml = post_soap_request(soap_request)
        
        # Check for SOAP fault
        fault = parse_soap_fault(response_xml)
        if fault:
            return error_response(fault['message'], fault['code'])
        
        # Parse available days
        root = ET.fromstring(response_xml)
        days = []
        
        # Try with namespace first
        for day_elem in root.findall('.//{http://zbooking2.zeitmechanik.net/}day'):
            if day_elem.text:
                days.append(day_elem.text.strip())
        
        # Fallback: try without namespace
        if not days:
            for day_elem in root.findall('.//day'):
                if day_elem.text:
                    days.append(day_elem.text.strip())
        
        # Add weekday and month information to each date
        # Filter out dates within 14 days from today
        from datetime import datetime, timedelta
        days_with_weekdays = []
        weekday_names_de = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        month_names_de = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 
                          'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
        
        # Calculate the minimum date (14 days from now)
        min_date = datetime.now().date() + timedelta(days=14)
        
        for day in days:
            try:
                date_obj = datetime.strptime(day, '%Y-%m-%d')
                
                # Skip dates within 14 days from today
                if date_obj.date() < min_date:
                    continue
                
                weekday_name = weekday_names_de[date_obj.weekday()]
                month_name = month_names_de[date_obj.month - 1]
                days_with_weekdays.append({
                    'date': day,
                    'weekday': weekday_name,
                    'month': month_name,
                    'day_of_month': date_obj.day
                })
            except:
                # Fallback if date parsing fails - skip these dates
                pass
        
        # Build services info
        services_info = [
            {'id': sid, 'name': SERVICES[sid]['name']}
            for sid in service_ids
        ]
        
        logger.info(f"Found {len(days_with_weekdays)} available days for services: {service_ids}")
        
        return success_response({
            'services': services_info,
            'available_days': days_with_weekdays,
            'count': len(days_with_weekdays)
        })
    
    except Exception as e:
        return error_response(str(e), 'AVAILABILITY_ERROR', status=500)


@app.route('/api/availability/times', methods=['GET', 'POST'])
def get_available_times():
    """
    Get available times for a specific day
    
    POST JSON body (recommended):
    {
        "date": "2025-11-20",
        "service_ids": ["2430983"]
    }
    """
    # Parse input
    if request.method == 'POST':
        data = extract_vapi_params() or {}
        logger.info(f"POST data for times: {data}")
        date = data.get('date')
        
        # Accept both service_id (string) and service_ids (array)
        service_ids_param = data.get('service_ids') or data.get('service_id')
        logger.info(f"Times - service_ids_param: {service_ids_param}")
        
        if isinstance(service_ids_param, list):
            service_ids = service_ids_param
        elif isinstance(service_ids_param, str):
            service_ids = [service_ids_param.strip()] if service_ids_param.strip() else None
        else:
            service_ids = None
    else:
        date = request.args.get('date')
        service_ids_param = request.args.get('service_ids')
        if service_ids_param:
            service_ids = [sid.strip() for sid in service_ids_param.split(',') if sid.strip()]
        else:
            service_ids = None
    
    logger.info(f"Times - Final service_ids: {service_ids}, date: {date}")
    
    # Validate input
    if not date:
        return error_response(
            'date parameter is required',
            'MISSING_PARAMETER',
            {'required': 'date', 'format': 'YYYY-MM-DD', 'example': '2025-11-20'}
        )
    
    if not service_ids:
        return error_response(
            'service_ids parameter is required',
            'MISSING_PARAMETER',
            {'required': 'service_ids', 'format': 'array of strings'}
        )
    
    # Validate date format
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return error_response(
            f'Invalid date format: {date}',
            'INVALID_DATE_FORMAT',
            {'expected': 'YYYY-MM-DD', 'example': '2025-11-20'}
        )
    
    valid, error_msg = validate_service_ids(service_ids)
    if not valid:
        return error_response(error_msg, 'INVALID_SERVICE_IDS')
    
    # Build SOAP request
    work_ids_xml = ''.join([f'<workId>{sid}</workId>' for sid in service_ids])
    
    soap_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:zbo="http://zbooking2.zeitmechanik.net/">
    <soapenv:Header/>
    <soapenv:Body>
        <zbo:searchAvailableTime>
            <token>{TOKEN}</token>
            <date>{date}</date>
            <workIds>{work_ids_xml}</workIds>
            <existingReservationId></existingReservationId>
            <vip></vip>
        </zbo:searchAvailableTime>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    try:
        response_xml = post_soap_request(soap_request)
        
        # Check for SOAP fault
        fault = parse_soap_fault(response_xml)
        if fault:
            return error_response(fault['message'], fault['code'])
        
        # Parse available times
        root = ET.fromstring(response_xml)
        times = []
        
        # Try with namespace
        for time_elem in root.findall('.//{http://zbooking2.zeitmechanik.net/}time'):
            if time_elem.text:
                times.append(time_elem.text.strip())
        
        # Fallback: without namespace
        if not times:
            for time_elem in root.findall('.//time'):
                if time_elem.text:
                    times.append(time_elem.text.strip())
        
        services_info = [
            {'id': sid, 'name': SERVICES[sid]['name']}
            for sid in service_ids
        ]
        
        logger.info(f"Found {len(times)} available times for {date}")
        
        return success_response({
            'date': date,
            'services': services_info,
            'available_times': times,
            'count': len(times)
        })
    
    except Exception as e:
        return error_response(str(e), 'AVAILABILITY_ERROR', status=500)


@app.route('/api/booking/reserve', methods=['POST'])
def reserve_appointment():
    """
    Reserve an appointment slot
    
    POST JSON body:
    {
        "time": "2025-11-20T09:00:00",
        "service_ids": ["2430983"]
    }
    """
    data = extract_vapi_params()
    
    if not data:
        return error_response('Request body is required', 'MISSING_BODY')
    
    logger.info(f"Reserve - POST data: {data}")
    
    time = data.get('time')
    # Accept both service_id (string) and service_ids (array)
    service_ids_param = data.get('service_ids') or data.get('service_id')
    
    logger.info(f"Reserve - time: {time}, service_ids_param: {service_ids_param}")
    
    if isinstance(service_ids_param, list):
        service_ids = service_ids_param
    elif isinstance(service_ids_param, str):
        service_ids = [service_ids_param.strip()] if service_ids_param.strip() else None
    else:
        service_ids = None
    
    logger.info(f"Reserve - Final service_ids: {service_ids}")
    
    # Validate input
    if not time:
        return error_response(
            'time parameter is required',
            'MISSING_PARAMETER',
            {'required': 'time', 'format': 'YYYY-MM-DDTHH:MM:SS', 'example': '2025-11-20T09:00:00'}
        )
    
    if not service_ids:
        return error_response(
            'service_ids parameter is required',
            'MISSING_PARAMETER'
        )
    
    # Validate time format
    try:
        datetime.fromisoformat(time)
    except ValueError:
        return error_response(
            f'Invalid time format: {time}',
            'INVALID_TIME_FORMAT',
            {'expected': 'YYYY-MM-DDTHH:MM:SS', 'example': '2025-11-20T09:00:00'}
        )
    
    valid, error_msg = validate_service_ids(service_ids)
    if not valid:
        return error_response(error_msg, 'INVALID_SERVICE_IDS')
    
    # Build SOAP request
    work_ids_xml = ''.join([f'<workId>{sid}</workId>' for sid in service_ids])
    expected_period = data.get('expected_reservation_period', 5)
    external_portal = data.get('external_portal', 'zbooking2')
    
    soap_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:zbo="http://zbooking2.zeitmechanik.net/">
    <soapenv:Header/>
    <soapenv:Body>
        <zbo:reserveAppointment>
            <token>{TOKEN}</token>
            <time>{time}</time>
            <workIds>{work_ids_xml}</workIds>
            <vip></vip>
            <existingReservationId></existingReservationId>
            <expectedReservationPeriod>{expected_period}</expectedReservationPeriod>
            <externalPortal>{external_portal}</externalPortal>
        </zbo:reserveAppointment>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    try:
        response_xml = post_soap_request(soap_request)
        
        # Check for SOAP fault
        fault = parse_soap_fault(response_xml)
        if fault:
            return error_response(fault['message'], fault['code'])
        
        # Parse reservation response
        root = ET.fromstring(response_xml)
        
        # Try with namespace first
        ns = {'ns1': 'http://zbooking2.zeitmechanik.net/'}
        appointment_id_elem = root.find('.//ns1:reserveAppointmentResponse/reservation/appointmentId', ns)
        date_time_elem = root.find('.//ns1:reserveAppointmentResponse/reservation/dateTime', ns)
        expiration_elem = root.find('.//ns1:reserveAppointmentResponse/reservation/expiration', ns)
        
        # Fallback: try without namespace
        if appointment_id_elem is None:
            appointment_id_elem = root.find('.//appointmentId')
            date_time_elem = root.find('.//dateTime')
            expiration_elem = root.find('.//expiration')
        
        # Extract values with null handling
        appointment_id = appointment_id_elem.text.strip() if appointment_id_elem is not None and appointment_id_elem.text else None
        date_time = date_time_elem.text.strip() if date_time_elem is not None and date_time_elem.text else None
        expiration = expiration_elem.text.strip() if expiration_elem is not None and expiration_elem.text else None
        
        if not appointment_id:
            return error_response(
                'Reservation failed: no appointment ID received',
                'RESERVATION_FAILED',
                {'time': time, 'services': service_ids}
            )
        
        services_info = [
            {'id': sid, 'name': SERVICES[sid]['name']}
            for sid in service_ids
        ]
        
        logger.info(f"Reserved appointment: {appointment_id} for {time}")
        
        # Store appointment_id globally (keyed by callsystem or fallback to 'latest')
        from flask import g
        call_id = getattr(g, 'call_id', None) or data.get('call_id', 'latest')
        ACTIVE_RESERVATIONS[call_id] = appointment_id
        logger.info(f"Stored appointment_id {appointment_id} for call_id: {call_id}")
        
        return success_response({
            'reservation': {
                'appointment_id': appointment_id,
                'date_time': date_time,
                'expiration': expiration,
                'services': services_info
            },
            '_stored_appointment_id': appointment_id,  # Explicit reminder
            '_hint': 'appointment_id has been automatically stored. Use it in bestaetigeTermin.'
        })
    
    except Exception as e:
        return error_response(str(e), 'RESERVATION_ERROR', status=500)


@app.route('/api/booking/confirm', methods=['POST'])
def confirm_appointment():
    """
    Confirm a reserved appointment
    
    POST JSON body (VAPI-friendly format):
    {
        "appointment_id": "377818444",
        "car": {
            "license_plate": "HH AB 1234",
            "make": "BMW",
            "model": "528i",
            "mileage": "50000"
        },
        "customer": {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.de",
            "phone": "+491234567890"
        },
        "comment": "",
        "customer_wants_to_wait": false,
        "customer_needs_rental": false,
        "storage_number": ""
    }
    """
    data = extract_vapi_params()
    
    if not data:
        return error_response('Request body is required', 'MISSING_BODY')
    
    logger.info(f"Confirm - POST data keys: {list(data.keys())}")
    
    appointment_id = data.get('appointment_id')
    car = data.get('car', {})
    customer = data.get('customer', {})
    
    logger.info(f"Confirm - appointment_id from request: {appointment_id}, car: {car.keys() if car else None}, customer: {customer.keys() if customer else None}")
    
    # ALWAYS use stored appointment_id from session (GPT-4 cannot be trusted to preserve it correctly)
    from flask import g
    call_id = getattr(g, 'call_id', None) or data.get('call_id', 'unknown_call')
    stored_id = ACTIVE_RESERVATIONS.get(call_id)
    
    if stored_id:
        if appointment_id and appointment_id != stored_id:
            logger.warning(f"GPT-4 sent wrong appointment_id {appointment_id}, overriding with stored {stored_id}")
        else:
            logger.info(f"Using stored appointment_id: {stored_id}")
        appointment_id = stored_id
    elif not appointment_id or not appointment_id.strip():
        return error_response(
            'No appointment_id found in session or request',
            'MISSING_APPOINTMENT_ID',
            {'hint': 'Must call reserviereTermin before bestaetigeTermin', 'call_id': call_id}
        )
    else:
        logger.warning(f"No stored appointment_id for call_id {call_id}, using request value: {appointment_id}")
    
    if not car:
        return error_response('car data is required', 'MISSING_CAR_DATA')
    
    if not customer:
        return error_response('customer data is required', 'MISSING_CUSTOMER_DATA')
    
    # Convert VAPI format to SOAP format
    # Car: make + model → type
    car_type = car.get('type')
    if not car_type:
        make = car.get('make', '').strip()
        model = car.get('model', '').strip()
        if make and model:
            car_type = f"{make} {model}"
        elif model:
            car_type = model
        elif make:
            car_type = make
        else:
            return error_response(
                'Car make and/or model required',
                'MISSING_CAR_TYPE'
            )
    
    # Customer: first_name + last_name → surname
    surname = customer.get('surname')
    if not surname:
        first = customer.get('first_name', '').strip()
        last = customer.get('last_name', '').strip()
        if first and last:
            surname = f"{first} {last}"
        elif last:
            surname = last
        elif first:
            surname = first
        else:
            return error_response(
                'Customer name required (surname OR first_name/last_name)',
                'MISSING_CUSTOMER_NAME'
            )
    
    # Phone: string → phones array
    phones = customer.get('phones', [])
    if not phones and customer.get('phone'):
        phone_str = customer.get('phone', '').strip()
        if phone_str:
            phones = [{"number": phone_str, "type": "mobile"}]
    
    # Build phones XML
    phones_xml = ''
    for phone in phones:
        number = phone.get('number', '').strip()
        if number:
            phones_xml += f"""<phones>
                <number>{number}</number>
                <type>{phone.get('type', 'mobile')}</type>
            </phones>"""
    
    # Validate required fields
    email = customer.get('email', '').strip()
    if not email:
        return error_response('Customer email is required', 'MISSING_EMAIL')
    
    license_plate = car.get('license_plate', '').strip()
    if not license_plate:
        return error_response('Car license_plate is required', 'MISSING_LICENSE_PLATE')
    
    # Get optional fields
    mileage = str(car.get('mileage', '0'))
    vin = car.get('vin', '')
    comment = data.get('comment', '')
    language = customer.get('language', 'de')
    customer_waits = str(data.get('customer_wants_to_wait', False)).lower()
    needs_rental = str(data.get('customer_needs_rental', False)).lower()
    storage_number = data.get('storage_number', '')
    
    # Build SOAP request
    soap_request = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:zbo="http://zbooking2.zeitmechanik.net/">
    <soapenv:Header/>
    <soapenv:Body>
        <zbo:confirmAppointment>
            <token>{TOKEN}</token>
            <appointmentId>{appointment_id}</appointmentId>
            <car>
                <licenseplate>{license_plate}</licenseplate>
                <type>{car_type}</type>
                <mileage>{mileage}</mileage>
                <vin>{vin}</vin>
            </car>
            <customer>
                <surname>{surname}</surname>
                {phones_xml}
                <email>{email}</email>
                <language>{language}</language>
            </customer>
            <comment>{comment}</comment>
            <additionalData>
                <key>customerWantsToWait</key>
                <value>{customer_waits}</value>
            </additionalData>
            <additionalData>
                <key>customerNeedsRental</key>
                <value>{needs_rental}</value>
            </additionalData>
            <additionalData>
                <key>storageNumber</key>
                <value>{storage_number}</value>
            </additionalData>
        </zbo:confirmAppointment>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    try:
        logger.info(f"Confirming appointment {appointment_id} for {surname}")
        response_xml = post_soap_request(soap_request)
        
        # Check for SOAP fault
        fault = parse_soap_fault(response_xml)
        if fault:
            return error_response(fault['message'], fault['code'])
        
        logger.info(f"Appointment {appointment_id} confirmed successfully")
        
        return success_response({
            'message': 'Appointment confirmed successfully',
            'appointment_id': appointment_id
        })
    
    except Exception as e:
        return error_response(str(e), 'CONFIRMATION_ERROR', status=500)


@app.route('/api/booking/full', methods=['POST'])
def full_booking_flow():
    """
    Complete booking flow: find → reserve → confirm
    Only use when customer wants earliest available
    """
    data = extract_vapi_params()
    
    if not data:
        return error_response('Request body is required', 'MISSING_BODY')
    
    logger.info(f"Full booking - POST data keys: {list(data.keys())}")
    
    service_ids = data.get('service_ids', [])
    car = data.get('car', {})
    customer = data.get('customer', {})
    
    # Validate input
    if not service_ids:
        return error_response('service_ids required', 'MISSING_PARAMETER')
    if not car:
        return error_response('car data required', 'MISSING_CAR_DATA')
    if not customer:
        return error_response('customer data required', 'MISSING_CUSTOMER_DATA')
    
    valid, error_msg = validate_service_ids(service_ids)
    if not valid:
        return error_response(error_msg, 'INVALID_SERVICE_IDS')
    
    try:
        # Step 1: Get available days
        logger.info("Quick booking: Step 1 - Finding available days")
        with app.test_request_context(json={'service_ids': service_ids}, method='POST'):
            days_response_tuple = get_available_days()
            days_response = days_response_tuple[0]
            days_data = days_response.get_json()
        
        if not days_data.get('success') or not days_data.get('available_days'):
            return error_response(
                'No available days found',
                'NO_AVAILABILITY',
                {'step': 'search_days'}
            )
        
        first_day = days_data['available_days'][0]
        logger.info(f"Quick booking: Found first available day: {first_day}")
        
        # Step 2: Get available times
        logger.info("Quick booking: Step 2 - Finding available times")
        with app.test_request_context(json={'date': first_day, 'service_ids': service_ids}, method='POST'):
            times_response_tuple = get_available_times()
            times_response = times_response_tuple[0]
            times_data = times_response.get_json()
        
        if not times_data.get('success') or not times_data.get('available_times'):
            return error_response(
                'No available times found',
                'NO_AVAILABILITY',
                {'step': 'search_times', 'date': first_day}
            )
        
        first_time = times_data['available_times'][0]
        logger.info(f"Quick booking: Found first available time: {first_time}")
        
        # Step 3: Reserve
        logger.info("Quick booking: Step 3 - Reserving appointment")
        reserve_data = {
            'time': first_time,
            'service_ids': service_ids
        }
        
        with app.test_request_context(json=reserve_data, method='POST'):
            reserve_response_tuple = reserve_appointment()
            reserve_response = reserve_response_tuple[0]
            reserve_result = reserve_response.get_json()
        
        if not reserve_result.get('success'):
            return error_response(
                'Failed to reserve appointment',
                'RESERVATION_FAILED',
                {'step': 'reserve', 'details': reserve_result}
            )
        
        appointment_id = reserve_result['reservation']['appointment_id']
        logger.info(f"Quick booking: Reserved appointment: {appointment_id}")
        
        # Step 4: Confirm
        logger.info("Quick booking: Step 4 - Confirming appointment")
        confirm_data = {
            'appointment_id': appointment_id,
            'car': car,
            'customer': customer,
            'comment': data.get('comment', ''),
            'customer_wants_to_wait': data.get('customer_wants_to_wait', False),
            'customer_needs_rental': data.get('customer_needs_rental', False),
            'storage_number': data.get('storage_number', '')
        }
        
        with app.test_request_context(json=confirm_data, method='POST'):
            confirm_response_tuple = confirm_appointment()
            confirm_response = confirm_response_tuple[0]
            confirm_result = confirm_response.get_json()
        
        if not confirm_result.get('success'):
            return error_response(
                'Failed to confirm appointment',
                'CONFIRMATION_FAILED',
                {'step': 'confirm', 'details': confirm_result}
            )
        
        logger.info(f"Quick booking: Complete! Appointment {appointment_id} confirmed")
        
        return success_response({
            'message': 'Quick booking completed successfully',
            'booking': {
                'appointment_id': appointment_id,
                'date_time': reserve_result['reservation']['date_time'],
                'expiration': reserve_result['reservation']['expiration'],
                'services': reserve_result['reservation']['services']
            }
        })
    
    except Exception as e:
        logger.error(f"Quick booking error: {e}")
        return error_response(str(e), 'QUICK_BOOKING_ERROR', status=500)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return success_response({
        'service': 'Zeitmechanik Booking Proxy',
        'version': '3.0.0',
        'status': 'healthy'
    })


@app.route('/', methods=['GET'])
def index():
    """API documentation"""
    return jsonify({
        'service': 'Zeitmechanik Booking Proxy Server',
        'version': '3.0.0 - Optimized for VAPI',
        'endpoints': {
            'GET /api/health': 'Health check',
            'GET /api/services': 'List all services',
            'GET /api/services/<id>': 'Get service details',
            'POST /api/availability/days': 'Find available days',
            'POST /api/availability/times': 'Find available times',
            'POST /api/booking/reserve': 'Reserve appointment (returns appointment_id)',
            'POST /api/booking/confirm': 'Confirm appointment (requires appointment_id)',
            'POST /api/booking/full': 'Quick booking (all in one)'
        },
        'features': [
            'Consistent response format (always includes success field)',
            'Specific error codes for debugging',
            'VAPI-friendly format (auto-converts first_name/last_name)',
            'Input validation',
            'Enhanced logging'
        ]
    })


if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Zeitmechanik Booking Proxy Server V3.0 - OPTIMIZED")
    print("=" * 80)
    print("\n📍 Server: http://localhost:5000")
    print("📖 Documentation: http://localhost:5000")
    print("\n✨ Improvements:")
    print("   ✓ Consistent response format")
    print("   ✓ Better error handling")
    print("   ✓ Enhanced validation")
    print("   ✓ Detailed logging")
    print("=" * 80 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
