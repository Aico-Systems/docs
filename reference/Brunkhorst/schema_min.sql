\restrict Opqeh4KMT09GRRlSPhlzEuEJ8bUGmh43oCOHnidZAECirOfoUS0s6twCjSnC1S1

CREATE SCHEMA public;

CREATE TYPE public.parts_selection AS ENUM (
    'PS_PARTSNUMBER',
    'PS_PARTSNUMBER_LENGTH',
    'PS_PARTS_TYPE',
    'PS_LAST_OUTGOING_DATE',
    'PS_LAST_INCOMING_DATE',
    'PS_STORAGE_NUMBER',
    'PS_STORAGE_BIN',
    'PS_STORAGE_BIN_2',
    'PS_USAGE_VALUE',
    'PS_VALUE',
    'PS_SELLING_PRICE',
    'PS_PARTS_FAMILIY',
    'PS_MANUFACTURER_PARTS_TYPE',
    'PS_STORAGE_FLAG',
    'PS_STORAGE_FLAG_SPECIAL',
    'PS_STOP_ORDER_FLAG',
    'PS_REBATE_CODE',
    'PS_ACCOUNTING_EXCEPTIONAL_GRP',
    'PS_STOCK_LEVEL_VISIBLE'
);



CREATE FUNCTION public.absence_calendar_modified() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN IF TG_OP = 'DELETE' THEN PERFORM pg_notify(CAST('ABSENCE_CALENDAR_CHANGED' AS TEXT), NEXTVAL('private.absence_calendar_msg') || ';DELETE;' || CAST(OLD.employee_number AS TEXT) || ';' || CAST(OLD.date AS TEXT) || ';' || CAST(OLD.unique_dummy AS TEXT) || ';' || CAST(OLD.time_from AS TEXT) || ';' || CAST(OLD.time_to AS TEXT) || ';' || ';' || ';'); RETURN OLD; ELSE IF TG_OP = 'UPDATE' THEN PERFORM pg_notify(CAST('ABSENCE_CALENDAR_CHANGED' AS TEXT), NEXTVAL('private.absence_calendar_msg') || ';' || TG_OP || ';' || CAST(NEW.employee_number AS TEXT) || ';' || CAST(NEW.date AS TEXT) || ';' || CAST(NEW.unique_dummy AS TEXT) || ';' || CAST(NEW.time_from AS TEXT) || ';' || CAST(NEW.time_to AS TEXT) || ';' || CAST(OLD.time_from AS TEXT) || ';' || CAST(OLD.time_to AS TEXT) || ';'); ELSE PERFORM pg_notify(CAST('ABSENCE_CALENDAR_CHANGED' AS TEXT), NEXTVAL('private.absence_calendar_msg') || ';' || TG_OP || ';' || CAST(NEW.employee_number AS TEXT) || ';' || CAST(NEW.date AS TEXT) || ';' || CAST(NEW.unique_dummy AS TEXT) || ';' || CAST(NEW.time_from AS TEXT) || ';' || CAST(NEW.time_to AS TEXT) || ';' || ';' || ';'); END IF; RETURN NEW; END IF; END; $$;



CREATE FUNCTION public.customer_contact_log_pemissions_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN IF TG_OP = 'DELETE' THEN UPDATE private.customer_contact_log AS l SET employee_permissions = (SELECT COUNT(*) FROM customer_contact_log_pemissions AS p WHERE p.customer_number = l.customer_number AND p.case_number = l.case_number) WHERE customer_number = OLD.customer_number AND case_number = OLD.case_number; RETURN OLD; ELSE IF TG_OP = 'INSERT' THEN UPDATE private.customer_contact_log AS l SET employee_permissions = (SELECT COUNT(*) FROM customer_contact_log_pemissions AS p WHERE p.customer_number = l.customer_number AND p.case_number = l.case_number) WHERE customer_number = NEW.customer_number AND case_number = NEW.case_number; RETURN NEW; END IF; END IF; END; $$;



CREATE FUNCTION public.track_table_changes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ DECLARE   v_schema_name TEXT := TG_TABLE_SCHEMA;   v_table_name TEXT := TG_TABLE_NAME; BEGIN   INSERT INTO app2.table_change_tracker (schema_name, table_name, last_modified)   VALUES (v_schema_name, v_table_name, now())   ON CONFLICT (schema_name, table_name)   DO UPDATE SET last_modified = now();   RETURN NEW; END; $$;



CREATE FUNCTION public.vehicle_contact_log_pemissions_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN IF TG_OP = 'DELETE' THEN UPDATE private.vehicle_contact_log AS l SET employee_permissions = (SELECT COUNT(*) FROM vehicle_contact_log_pemissions AS p WHERE p.vehicle_number = l.vehicle_number AND p.case_number = l.case_number) WHERE vehicle_number = OLD.vehicle_number AND case_number = OLD.case_number; RETURN OLD; ELSE IF TG_OP = 'INSERT' THEN UPDATE private.vehicle_contact_log AS l SET employee_permissions = (SELECT COUNT(*) FROM vehicle_contact_log_pemissions AS p WHERE p.vehicle_number = l.vehicle_number AND p.case_number = l.case_number) WHERE vehicle_number = NEW.vehicle_number AND case_number = NEW.case_number; RETURN NEW; END IF; END IF; END; $$;



CREATE FUNCTION public.workshop_modified() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN IF TG_OP = 'DELETE' THEN PERFORM pg_notify(CAST('APPOINTMENTS_WORKSHOP_PROCESS' AS TEXT), NEXTVAL('appointment_workshop_msg') || ';DELETE;' || CAST(OLD.id AS TEXT) || ';' || OLD.subsidiary || ';' || CAST(COALESCE(OLD.bring_timestamp, DATE(NOW())) AS TEXT) || ';' || CAST(COALESCE(OLD.return_timestamp, DATE(NOW())) AS TEXT) || ';' || CAST(OLD.appointment_type AS TEXT) || ';' || CAST(COALESCE(OLD.vehicle_number, 0) AS TEXT)); RETURN OLD; ELSE IF TG_OP = 'INSERT' OR NEW.lock_by_workstation IS NULL THEN PERFORM pg_notify(CAST('APPOINTMENTS_WORKSHOP_PROCESS' AS TEXT), NEXTVAL('appointment_workshop_msg') || ';' || TG_OP || ';' || CAST(NEW.id AS TEXT) || ';' || NEW.subsidiary || ';' || CAST(COALESCE(NEW.bring_timestamp, DATE(NOW())) AS TEXT) || ';' || CAST(COALESCE(NEW.return_timestamp, DATE(NOW())) AS TEXT) || ';' || CAST(NEW.appointment_type AS TEXT) || ';' || CAST(COALESCE(NEW.vehicle_number, 0) AS TEXT)); END IF; RETURN NEW; END IF; END; $$;




CREATE TABLE public.absence_calendar (
    employee_number integer NOT NULL,
    date date NOT NULL,
    unique_dummy integer NOT NULL,
    type character varying(1),
    is_payed boolean,
    day_contingent numeric(4,2),
    reason_type integer,
    reason character varying(3),
    booking_flag character varying(1),
    time_from timestamp without time zone,
    time_to timestamp without time zone,
    CONSTRAINT absence_calendar_booking_flag_check CHECK ((((booking_flag)::text = 'A'::text) OR ((booking_flag)::text = 'J'::text)))
);



CREATE TABLE public.absence_reasons (
    id character varying(3) NOT NULL,
    description character varying(15),
    is_annual_vacation boolean,
    CONSTRAINT absence_reasons_id_check CHECK (((id)::text > ''::text))
);



CREATE TABLE public.absence_types (
    type character varying(1) NOT NULL,
    description character varying(20),
    CONSTRAINT absence_types_type_check CHECK (((type)::text > ''::text))
);



CREATE TABLE public.accounts_characteristics (
    subsidiary_to_company_ref bigint NOT NULL,
    skr51_branch bigint NOT NULL,
    skr51_make bigint NOT NULL,
    skr51_cost_center bigint NOT NULL,
    skr51_sales_channel bigint NOT NULL,
    skr51_cost_unit bigint NOT NULL,
    skr51_branch_name text,
    skr51_make_description text,
    skr51_cost_center_name text,
    skr51_sales_channel_name text,
    skr51_cost_unit_name text
);



CREATE UNLOGGED SEQUENCE public.appointment_workshop_msg
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999999
    CACHE 1
    CYCLE;



CREATE TABLE public.appointments (
    id integer NOT NULL,
    subsidiary integer,
    appointment_type integer,
    customer_number integer,
    vehicle_number integer,
    comment character varying(80),
    created_by_employee integer,
    created_timestamp timestamp without time zone,
    modified_by_employee integer,
    modified_timestamp timestamp without time zone,
    locked_by_employee integer,
    blocked_timestamp timestamp without time zone,
    bring_timestamp timestamp without time zone,
    return_timestamp timestamp without time zone,
    pseudo_customer_name character varying(45),
    pseudo_customer_country character varying(3),
    pseudo_customer_zip_code character varying(20),
    pseudo_customer_home_city character varying(25),
    pseudo_customer_home_street character varying(27),
    pseudo_vehicle_make_number integer,
    pseudo_vehicle_make_text character varying(10),
    pseudo_model_code character varying(16),
    pseudo_model_text character varying(18),
    pseudo_license_plate character varying(12),
    pseudo_vin character varying(17),
    order_number integer,
    is_customer_reminder_allowed boolean,
    customer_reminder_type character varying(30),
    customer_reminder_timestamp timestamp without time zone,
    bring_duration integer,
    bring_employee_no integer,
    return_duration integer,
    return_employee_no integer,
    customer_pickup_bring integer,
    is_general_inspection_service boolean,
    urgency integer,
    vehicle_status integer,
    progress_status integer,
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10)
);



CREATE TABLE public.appointments_text (
    appointment_id integer NOT NULL,
    description character varying(376),
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10)
);



CREATE TABLE public.charge_type_descriptions (
    type integer NOT NULL,
    description character varying(40)
);



CREATE TABLE public.charge_types (
    type integer NOT NULL,
    subsidiary integer NOT NULL,
    timeunit_rate numeric(9,3),
    department integer,
    CONSTRAINT charge_types_department_check CHECK (((department = 0) OR ((department >= 1) AND (department <= 6)) OR (department = 9)))
);



CREATE TABLE public.clearing_delay_types (
    type character(1) NOT NULL,
    description character varying(42)
);



CREATE TABLE public.codes_customer_def (
    code character varying(5) NOT NULL,
    is_defined_by_dms boolean,
    format character varying(1),
    length integer,
    "decimal" integer,
    description character varying(44)
);



CREATE TABLE public.codes_customer_list (
    customer_number integer NOT NULL,
    code character varying(5) NOT NULL,
    value_format character varying(1),
    value_text character varying(40),
    value_numeric numeric(18,9),
    value_date date
);



CREATE TABLE public.codes_vehicle_date (
    vehicle_number integer NOT NULL,
    code character varying(5) NOT NULL,
    date date
);



CREATE TABLE public.codes_vehicle_date_def (
    code character varying(5) NOT NULL,
    is_defined_by_dms boolean,
    month_increase_factor integer,
    show_in_211_from_or_to character varying(1),
    is_backdate_on_exceeding boolean,
    description character varying(44)
);



CREATE TABLE public.codes_vehicle_def (
    code character varying(5) NOT NULL,
    is_defined_by_dms boolean,
    format character varying(1),
    length integer,
    "decimal" integer,
    description character varying(44)
);



CREATE TABLE public.codes_vehicle_list (
    vehicle_number integer NOT NULL,
    code character varying(5) NOT NULL,
    value_format character varying(1),
    value_text character varying(40),
    value_numeric numeric(18,9),
    value_date date
);



CREATE TABLE public.codes_vehicle_mileage (
    vehicle_number integer NOT NULL,
    code character varying(5) NOT NULL,
    kilometer integer
);



CREATE TABLE public.codes_vehicle_mileage_def (
    code character varying(5) NOT NULL,
    is_defined_by_dms boolean,
    mileage_increase_factor integer,
    show_in_211_from_or_to character varying(1),
    description character varying(44)
);



CREATE TABLE public.com_number_types (
    typ character varying(1) NOT NULL,
    description character varying(50),
    is_office_number boolean,
    CONSTRAINT com_number_types_typ_check CHECK (((typ)::text > ''::text))
);



CREATE TABLE public.configuration (
    type character varying(40) NOT NULL,
    value_numeric bigint NOT NULL,
    value_text text NOT NULL,
    description text,
    CONSTRAINT configuration_type_check CHECK (((type)::text > ''::text))
);



CREATE TABLE public.configuration_numeric (
    parameter_number integer NOT NULL,
    subsidiary integer NOT NULL,
    text_value character varying(18),
    description character varying(49)
);



CREATE TABLE public.countries (
    code character varying(3) NOT NULL,
    description character varying(40),
    iso3166_alpha2 character varying(2)
);



CREATE TABLE public.customer_codes (
    code integer NOT NULL,
    description character varying(42)
);



CREATE TABLE public.customer_com_numbers (
    customer_number integer NOT NULL,
    counter bigint NOT NULL,
    com_type character varying(1),
    is_reference boolean,
    only_on_1st_tab boolean,
    address character varying(300),
    has_contact_person_fields boolean,
    contact_salutation character varying(20),
    contact_firstname character varying(80),
    contact_lastname character varying(80),
    contact_description character varying(80),
    note character varying(80),
    search_address character varying(300),
    phone_number character varying(30)
);



CREATE TABLE public.customer_contact_log_pemissions (
    customer_number integer NOT NULL,
    case_number integer NOT NULL,
    employee_no integer NOT NULL
);



CREATE TABLE public.customer_profession_codes (
    code integer NOT NULL,
    description character varying(42)
);



CREATE TABLE public.customer_supplier_bank_information (
    customer_number integer NOT NULL,
    iban character varying(35),
    swift character varying(15),
    sepa_mandate_start_date date,
    note character varying(40)
);



CREATE TABLE public.customer_to_customercodes (
    customer_number integer NOT NULL,
    customer_code integer NOT NULL
);



CREATE TABLE public.customer_to_professioncodes (
    customer_number integer NOT NULL,
    profession_code integer NOT NULL
);



CREATE VIEW public.customer_top_note AS
 SELECT customer_number,
    string_agg(text, ' '::text) AS text
   FROM private.customer_contact_log
  GROUP BY customer_number, case_number
 HAVING (case_number = 0)
  ORDER BY customer_number, case_number;



CREATE TABLE public.customers_suppliers (
    customer_number integer NOT NULL,
    subsidiary integer,
    is_supplier boolean,
    is_natural_person boolean,
    is_dummy_customer boolean,
    salutation_code character varying(2),
    name_prefix character varying(40) COLLATE pg_catalog."de-x-icu",
    first_name character varying(40) COLLATE pg_catalog."de-x-icu",
    family_name character varying(40) COLLATE pg_catalog."de-x-icu",
    name_postfix character varying(40) COLLATE pg_catalog."de-x-icu",
    country_code character varying(3),
    zip_code character varying(20),
    home_city character varying(40) COLLATE pg_catalog."de-x-icu",
    home_street character varying(40) COLLATE pg_catalog."de-x-icu",
    contact_salutation_code character varying(2),
    contact_family_name character varying(30) COLLATE pg_catalog."de-x-icu",
    contact_first_name character varying(30) COLLATE pg_catalog."de-x-icu",
    contact_note character varying(30) COLLATE pg_catalog."de-x-icu",
    contact_personal_known boolean,
    parts_rebate_group_buy integer,
    parts_rebate_group_sell integer,
    rebate_labour_percent numeric(9,5),
    rebate_material_percent numeric(9,5),
    rebate_new_vehicles_percent numeric(9,5),
    cash_discount_percent numeric(9,5),
    vat_id_number character varying(20),
    vat_id_number_checked_date date,
    vat_id_free_code_1 integer,
    vat_id_free_code_2 integer,
    birthday date,
    last_contact date,
    preferred_com_number_type character varying(1),
    created_date date,
    created_employee_no integer,
    updated_date date,
    updated_employee_no integer,
    name_updated_date date,
    name_updated_employee_no integer,
    sales_assistant_employee_no integer,
    service_assistant_employee_no integer,
    parts_assistant_employee_no integer,
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10),
    location_latitude numeric(8,5),
    location_longitude numeric(8,5),
    order_classification_flag character(1),
    access_limit integer,
    fullname_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (((((((name_prefix)::text || ' '::text) || (first_name)::text) || ' '::text) || (family_name)::text) || ' '::text) || (name_postfix)::text))) STORED
);



CREATE TABLE public.dealer_sales_aid (
    dealer_vehicle_type character varying(1) NOT NULL,
    dealer_vehicle_number integer NOT NULL,
    code character varying(8) NOT NULL,
    claimed_amount numeric(9,2),
    available_until date,
    granted_amount numeric(9,2),
    was_paid_on date,
    note character varying(160) NOT NULL
);



CREATE TABLE public.dealer_sales_aid_bonus (
    dealer_vehicle_type character varying(1) NOT NULL,
    dealer_vehicle_number integer NOT NULL,
    code character varying(8) NOT NULL,
    claimed_amount numeric(9,2),
    available_until date,
    granted_amount numeric(9,2),
    was_paid_on date,
    note character varying(160) NOT NULL
);



CREATE TABLE public.dealer_vehicles (
    dealer_vehicle_type character varying(1) NOT NULL,
    dealer_vehicle_number integer NOT NULL,
    vehicle_number integer,
    location character varying(10),
    buyer_customer_no integer,
    deregistration_date date,
    refinancing_start_date date,
    refinancing_end_date date,
    refinancing_value numeric(9,2),
    refinancing_refundment numeric(9,2),
    refinancing_bank_customer_no integer,
    refinanc_interest_free_date date,
    in_subsidiary integer,
    in_buy_salesman_number integer,
    in_buy_order_no character varying(15),
    in_buy_order_no_date date,
    in_buy_invoice_no character varying(12),
    in_buy_invoice_no_date date,
    in_buy_edp_order_no character varying(15),
    in_buy_edp_order_no_date date,
    in_is_trade_in_ken character varying(1),
    in_is_trade_in_kom integer,
    in_used_vehicle_buy_type character varying(2),
    in_buy_list_price numeric(9,2),
    in_arrival_date date,
    in_expected_arrival_date date,
    in_accounting_document_type character varying(1),
    in_accounting_document_number bigint,
    in_accounting_document_date date,
    in_acntg_exceptional_group character varying(4),
    in_acntg_cost_unit_new_vehicle numeric(2,0),
    in_accounting_make numeric(2,0),
    in_registration_reference character varying(10),
    in_expected_repair_cost numeric(9,2),
    in_order_status character varying(4),
    out_subsidiary integer,
    out_is_ready_for_sale boolean,
    out_ready_for_sale_date date,
    out_sale_type character varying(1),
    out_sales_contract_number character varying(12),
    out_sales_contract_date date,
    out_is_sales_contract_confrmed boolean,
    out_salesman_number_1 integer,
    out_salesman_number_2 integer,
    out_desired_shipment_date date,
    out_is_registration_included boolean,
    out_recommended_retail_price numeric(9,2),
    out_extra_expenses numeric(9,2),
    out_sale_price numeric(9,2),
    out_sale_price_dealer numeric(9,2),
    out_sale_price_minimum numeric(9,2),
    out_sale_price_internet numeric(9,2),
    out_estimated_invoice_value numeric(9,2),
    out_discount_percent_vehicle numeric(9,5),
    out_discount_percent_accessory numeric(9,5),
    out_order_number integer,
    out_invoice_type integer,
    out_invoice_number integer,
    out_invoice_date date,
    out_deposit_invoice_type integer,
    out_deposit_invoice_number integer,
    out_deposit_value numeric(9,2),
    out_license_plate character varying(12),
    out_make_number integer,
    out_model_code character varying(25),
    out_license_plate_country character varying(3),
    out_license_plate_season character varying(6),
    calc_basic_charge numeric(9,2),
    calc_accessory numeric(9,2),
    calc_extra_expenses numeric(9,2),
    calc_insurance numeric(9,2),
    calc_usage_value_encr_external numeric(9,2),
    calc_usage_value_encr_internal numeric(9,2),
    calc_usage_value_encr_other numeric(9,2),
    calc_total_writedown numeric(9,2),
    calc_cost_percent_stockingdays numeric(3,0),
    calc_interest_percent_stkdays numeric(6,3),
    calc_actual_payed_interest numeric(9,2),
    calc_commission_for_arranging numeric(9,2),
    calc_commission_for_salesman numeric(9,2),
    calc_cost_internal_invoices numeric(9,2),
    calc_cost_other numeric(9,2),
    calc_sales_aid numeric(9,2),
    calc_sales_aid_finish numeric(9,2),
    calc_sales_aid_bonus numeric(9,2),
    calc_returns_workshop numeric(9,2),
    exclusive_reserved_employee_no integer,
    exclusive_reserved_until date,
    pre_owned_car_code character varying(1),
    is_sale_internet boolean,
    is_sale_prohibit boolean,
    is_agency_business boolean,
    is_rental_or_school_vehicle boolean,
    previous_owner_number integer,
    mileage_km integer,
    memo character varying(80),
    keys_box_number integer,
    last_change_date date,
    last_change_employee_no integer,
    created_date date,
    created_employee_no integer,
    has_financing_example boolean,
    has_leasing_example_ref boolean,
    deactivated_by_employee_no integer,
    deactivated_date date,
    access_limit integer,
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10)
);



CREATE TABLE public.document_types (
    document_type_in_journal text NOT NULL,
    document_type_description text
);



CREATE TABLE public.employees_history (
    is_latest_record boolean,
    employee_number integer NOT NULL,
    validity_date date NOT NULL,
    next_validity_date date,
    subsidiary integer,
    has_constant_salary boolean,
    name character varying(25),
    initials character varying(3),
    customer_number integer,
    employee_personnel_no integer,
    mechanic_number integer,
    salesman_number integer,
    is_business_executive boolean,
    is_master_craftsman boolean,
    is_customer_reception boolean,
    employment_date date,
    termination_date date,
    leave_date date,
    is_flextime boolean,
    break_time_registration character varying(10),
    productivity_factor numeric(2,1),
    schedule_index integer,
    CONSTRAINT employees_history_employee_number_check CHECK ((employee_number > 0))
);



CREATE VIEW public.employees AS
 SELECT is_latest_record,
    employee_number,
    validity_date,
    next_validity_date,
    subsidiary,
    has_constant_salary,
    name,
    initials,
    customer_number,
    employee_personnel_no,
    mechanic_number,
    salesman_number,
    is_business_executive,
    is_master_craftsman,
    is_customer_reception,
    employment_date,
    termination_date,
    leave_date,
    is_flextime,
    break_time_registration,
    productivity_factor,
    schedule_index
   FROM public.employees_history
  WHERE (is_latest_record = true);



CREATE TABLE public.employees_breaktimes (
    is_latest_record boolean,
    employee_number integer NOT NULL,
    validity_date date NOT NULL,
    dayofweek integer NOT NULL,
    break_start numeric(5,3) NOT NULL,
    break_end numeric(5,3),
    CONSTRAINT employees_breaktimes_employee_number_check CHECK ((employee_number > 0))
);



CREATE TABLE public.employees_group_mapping (
    employee_number integer NOT NULL,
    validity_date date NOT NULL,
    grp_code character varying(3) NOT NULL
);



CREATE TABLE public.employees_worktimes (
    is_latest_record boolean,
    employee_number integer NOT NULL,
    validity_date date NOT NULL,
    dayofweek integer NOT NULL,
    work_duration numeric(5,3),
    worktime_start numeric(5,3),
    worktime_end numeric(5,3),
    CONSTRAINT employees_worktimes_employee_number_check CHECK ((employee_number > 0))
);



CREATE TABLE public.external_customer_references (
    api_type character varying(4) NOT NULL,
    api_id character varying(10) NOT NULL,
    customer_number integer NOT NULL,
    subsidiary integer NOT NULL,
    reference character varying(100),
    last_received_time timestamp without time zone,
    version character varying(30)
);



CREATE TABLE public.external_reference_parties (
    api_type character varying(4) NOT NULL,
    api_id character varying(10) NOT NULL,
    make character varying(4),
    description character varying(50)
);



CREATE TABLE public.financing_examples (
    id integer NOT NULL,
    initial_payment numeric(9,2),
    loan_amount numeric(9,2),
    number_rates integer,
    annual_percentage_rate numeric(4,2),
    debit_interest numeric(4,2),
    debit_interest_type character varying(20),
    monthly_rate numeric(9,2),
    differing_first_rate numeric(9,2),
    last_rate numeric(9,2),
    rate_insurance numeric(9,2),
    acquisition_fee numeric(9,2),
    total numeric(9,2),
    interest_free_credit_until date,
    interest_free_credit_amount numeric(9,2),
    due_date integer,
    due_date_last_rate integer,
    bank_customer_no integer,
    source character varying(15),
    referenced_dealer_vehicle_type character varying(1),
    referenced_dealer_vehicle_no integer
);



CREATE SEQUENCE public.financing_examples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.financing_examples_id_seq OWNED BY public.financing_examples.id;



CREATE TABLE public.fuels (
    code character varying(1) NOT NULL,
    description character varying(200),
    CONSTRAINT fuels_code_check CHECK (((code)::text > ''::text))
);



CREATE TABLE public.invoice_types (
    type integer NOT NULL,
    description character varying(200),
    CONSTRAINT invoice_types_type_check CHECK ((type > 0))
);



CREATE TABLE public.invoices (
    invoice_type integer NOT NULL,
    invoice_number integer NOT NULL,
    subsidiary integer,
    order_number integer,
    paying_customer integer,
    invoice_date date,
    service_date date,
    is_canceled boolean,
    cancelation_number integer,
    cancelation_date date,
    cancelation_employee integer,
    is_own_vehicle boolean,
    is_credit boolean,
    credit_invoice_type integer,
    credit_invoice_number integer,
    odometer_reading integer,
    creating_employee integer,
    internal_cost_account integer,
    vehicle_number integer,
    full_vat_basevalue numeric(9,2),
    full_vat_percentage numeric(4,2),
    full_vat_value numeric(18,2),
    reduced_vat_basevalue numeric(9,2),
    reduced_vat_percentage numeric(4,2),
    reduced_vat_value numeric(18,2),
    used_part_vat_value numeric(9,2),
    job_amount_net numeric(18,2),
    job_amount_gross numeric(18,2),
    job_rebate numeric(9,2),
    part_amount_net numeric(18,2),
    part_amount_gross numeric(18,2),
    part_rebate numeric(9,2),
    part_disposal numeric(9,2),
    total_gross numeric(18,2),
    total_net numeric(18,2),
    parts_rebate_group_sell integer,
    internal_created_time timestamp without time zone,
    internal_canceled_time timestamp without time zone,
    order_classification_flag character(1),
    CONSTRAINT invoices_invoice_number_check CHECK ((invoice_number > 0))
);



CREATE TABLE public.journal_accountings (
    subsidiary_to_company_ref bigint NOT NULL,
    accounting_date date NOT NULL,
    document_type text NOT NULL,
    document_number bigint NOT NULL,
    position_in_document bigint NOT NULL,
    customer_number bigint,
    nominal_account_number bigint,
    is_balanced text,
    clearing_number bigint,
    document_date date,
    posted_value bigint,
    debit_or_credit text,
    posted_count bigint,
    branch_number bigint,
    customer_contra_account bigint,
    nominal_contra_account bigint,
    contra_account_text text,
    account_form_page_number bigint,
    account_form_page_line bigint,
    serial_number_each_month text,
    employee_number bigint,
    invoice_date date,
    invoice_number text,
    dunning_level text,
    last_dunning_date date,
    journal_page bigint,
    journal_line bigint,
    cash_discount bigint,
    term_of_payment bigint,
    posting_text text,
    vehicle_reference text,
    vat_id_number text,
    account_statement_number bigint,
    account_statement_page bigint,
    vat_key text,
    days_for_cash_discount bigint,
    day_of_actual_accounting date,
    skr51_branch bigint,
    skr51_make bigint,
    skr51_cost_center bigint,
    skr51_sales_channel bigint,
    skr51_cost_unit bigint,
    previously_used_account_no text,
    free_form_accounting_text text,
    free_form_document_text text
);



CREATE TABLE public.labour_types (
    code character varying(2) NOT NULL,
    description character varying(200),
    CONSTRAINT labour_types_code_check CHECK (((code)::text > ''::text))
);



CREATE TABLE public.labours (
    order_number integer NOT NULL,
    order_position integer NOT NULL,
    order_position_line integer NOT NULL,
    subsidiary integer,
    is_invoiced boolean,
    invoice_type integer,
    invoice_number integer,
    employee_no integer,
    mechanic_no integer,
    labour_operation_id character varying(20),
    is_nominal boolean,
    time_units numeric(9,2),
    net_price_in_order numeric(9,2),
    rebate_percent numeric(9,6),
    goodwill_percent numeric(9,6),
    charge_type integer,
    text_line character varying(80),
    usage_value numeric(9,2),
    negative_flag character varying(1),
    labour_type character varying(2)
);



CREATE TABLE public.labours_groups (
    source_number integer NOT NULL,
    labour_number_range character varying(15) NOT NULL,
    description text,
    source character varying(4)
);



CREATE TABLE public.labours_master (
    source_number integer NOT NULL,
    labour_number character varying(15) NOT NULL,
    mapping_code character varying(10) NOT NULL,
    text text,
    source character varying(4),
    text_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, text)) STORED
);



CREATE TABLE public.leasing_examples (
    id integer NOT NULL,
    number_rates integer,
    annual_mileage integer,
    special_payment numeric(9,2),
    calculation_basis numeric(9,2),
    calculation_basis_factor numeric(4,2),
    gross_residual_value numeric(9,2),
    gross_residual_value_factor numeric(4,2),
    monthly_rate numeric(9,2),
    exceeding_mileage numeric(9,2),
    under_usage_mileage numeric(9,2),
    bank_customer_no integer,
    source character varying(15),
    referenced_dealer_vehicle_type character varying(1),
    referenced_dealer_vehicle_no integer
);



CREATE SEQUENCE public.leasing_examples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.leasing_examples_id_seq OWNED BY public.leasing_examples.id;



CREATE TABLE public.makes (
    make_number integer NOT NULL,
    is_actual_make boolean,
    description character varying(200),
    group_name character varying(4),
    make_id_in_group character varying(4),
    internal_labour_group integer,
    is_production_year_visible boolean,
    is_transmission_no_visible boolean,
    is_engine_no_visible boolean,
    is_ricambi_no_visible boolean,
    ricambi_label character varying(40),
    is_preset_finance_stock_rate boolean,
    rate_free_days_new_vehicle integer,
    rate_free_days_demo_vehicle integer,
    special_service_2_interval numeric(4,1),
    special_service_3_interval numeric(4,1),
    CONSTRAINT makes_make_number_check CHECK ((make_number > 0))
);



CREATE TABLE public.model_to_fuels (
    make_number integer NOT NULL,
    model_code character varying(25) NOT NULL,
    code character varying(1) NOT NULL
);



CREATE TABLE public.models (
    make_number integer NOT NULL,
    model_code character varying(25) NOT NULL,
    is_actual_model boolean,
    model_currently_available boolean,
    replacing_model_code character varying(25),
    description character varying(200),
    gear_count integer,
    seat_count integer,
    door_count integer,
    cylinder_count integer,
    vehicle_body character varying(2),
    model_labour_group character varying(4),
    has_hour_meter boolean,
    source_extern boolean,
    free_form_vehicle_class character varying(4),
    vin_begin character varying(11),
    vehicle_pool_code character varying(25),
    vehicle_pool_engine_code character varying(5),
    is_manual_transmission boolean,
    is_all_wheel_drive boolean,
    is_plugin_hybride boolean,
    unloaded_weight integer,
    gross_vehicle_weight integer,
    power_kw integer,
    power_kw_at_rotation integer,
    cubic_capacity integer,
    german_kba_hsn character varying(4),
    german_kba_tsn character varying(15),
    annual_tax numeric(9,2),
    model_year numeric(4,0),
    model_year_postfix character varying(1),
    suggested_net_retail_price numeric(9,2),
    suggested_net_shipping_cost numeric(9,2),
    european_pollutant_class character varying(4),
    emission_code character varying(4),
    carbondioxid_emission integer,
    nox_exhoust numeric(5,3),
    particle_exhoust numeric(4,3),
    external_schwacke_code character varying(20),
    skr_carrier_flag numeric(2,0),
    free_form_model_specification character varying(3),
    external_technical_type character varying(4),
    european_fuel_consumption_over numeric(4,2),
    european_fuel_consumption_coun numeric(4,2),
    european_fuel_consumption_city numeric(4,2),
    energy_consumption numeric(5,2),
    insurance_class_liability integer,
    insurance_class_part_comprehen integer,
    insurance_class_full_comprehen integer,
    fuel_code_1 character(1),
    fuel_code_2 character(1),
    description_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (description)::text)) STORED,
    CONSTRAINT models_model_code_check CHECK (((model_code)::text > ''::text))
);



CREATE TABLE public.nominal_accounts (
    subsidiary_to_company_ref bigint NOT NULL,
    nominal_account_number bigint NOT NULL,
    account_description text,
    is_profit_loss_account text,
    vat_key text,
    create_date date,
    create_employee_number bigint,
    oldest_accountable_month date
);



CREATE TABLE public.order_classifications_def (
    code character(1) NOT NULL,
    description character varying(40),
    surcharge_type character(1),
    is_bulk_buyer boolean,
    is_special_sale boolean,
    target_group character(1),
    same_calculation_as_other character(1),
    special_price_rebate_type character(1),
    skr51_sales_channel integer,
    user_group character(1),
    with_disposal_cost boolean
);



CREATE TABLE public.orders (
    number integer NOT NULL,
    subsidiary integer,
    order_date timestamp without time zone,
    created_employee_no integer,
    updated_employee_no integer,
    estimated_inbound_time timestamp without time zone,
    estimated_outbound_time timestamp without time zone,
    order_print_date date,
    order_taking_employee_no integer,
    order_delivery_employee_no integer,
    vehicle_number integer,
    dealer_vehicle_type character varying(1),
    dealer_vehicle_number integer,
    order_mileage integer,
    order_customer integer,
    paying_customer integer,
    parts_rebate_group_sell integer,
    clearing_delay_type character varying(1),
    urgency integer,
    has_empty_positions boolean,
    has_open_positions boolean,
    has_closed_positions boolean,
    is_over_the_counter_order boolean,
    order_classification_flag character(1),
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10)
);



CREATE TABLE public.part_types (
    type integer NOT NULL,
    description character varying(42)
);



CREATE TABLE public.parts (
    order_number integer NOT NULL,
    order_position integer NOT NULL,
    order_position_line integer NOT NULL,
    subsidiary integer,
    is_invoiced boolean,
    invoice_type integer,
    invoice_number integer,
    employee_no integer,
    mechanic_no integer,
    part_number character varying(20) COLLATE pg_catalog."C",
    stock_no integer,
    stock_removal_date date,
    amount numeric(9,2),
    sum numeric(9,2),
    rebate_percent numeric(9,6),
    goodwill_percent numeric(9,6),
    parts_type integer,
    text_line character varying(32),
    usage_value numeric(9,2)
);



CREATE TABLE public.parts_additional_descriptions (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    description character varying(50),
    search_description character varying(50) COLLATE pg_catalog."C",
    description_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (description)::text)) STORED
);



CREATE TABLE public.parts_inbound_delivery_notes (
    supplier_number integer NOT NULL,
    year_key integer NOT NULL,
    number_main character varying(10) NOT NULL,
    number_sub character varying(4) NOT NULL,
    counter integer NOT NULL,
    purchase_invoice_year integer,
    purchase_invoice_number character varying(12),
    part_number character varying(20) COLLATE pg_catalog."C",
    stock_no integer,
    amount numeric(9,2),
    delivery_note_date date,
    parts_order_number integer,
    parts_order_note character varying(15),
    deliverers_note character varying(12),
    referenced_order_number integer,
    referenced_order_position integer,
    referenced_order_line integer,
    is_veryfied boolean,
    parts_order_type integer,
    rr_gross_price numeric(9,2),
    purchase_total_net_price numeric(9,2),
    parts_type integer,
    employee_number_veryfied integer,
    employee_number_imported integer,
    employee_number_last integer
);



CREATE TABLE public.parts_master (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    description character varying(32) COLLATE pg_catalog."de-x-icu",
    rebate_percent numeric(9,5),
    package_unit_type character varying(2),
    package_size integer,
    delivery_size integer,
    weight numeric(9,3),
    warranty_flag character varying(2),
    last_import_date date,
    price_valid_from_date date,
    storage_flag character varying(1),
    rebate_code character varying(4),
    parts_type integer,
    manufacturer_parts_type character varying(4),
    rr_price numeric(9,3),
    price_surcharge_percent numeric(9,5),
    selling_price_base_upe boolean,
    is_price_based_on_usage_value boolean,
    is_price_based_on_spcl_price boolean,
    has_price_common_surcharge boolean,
    allow_price_under_margin boolean,
    allow_price_under_usage_value boolean,
    is_stock_neutral boolean,
    is_stock_neutral_usage_v boolean,
    skr_carrier_flag numeric(2,0),
    price_import_keeps_description boolean,
    country_of_origin character varying(5),
    manufacturer_assembly_group character varying(7),
    has_information_ref boolean,
    has_costs_ref boolean,
    has_special_prices_ref boolean,
    has_special_offer_ref boolean,
    search_description character varying(32) COLLATE pg_catalog."C",
    description_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (description)::text)) STORED
);



CREATE TABLE public.parts_rebate_codes_buy (
    rebate_group_code integer NOT NULL,
    rebate_code character varying(5) NOT NULL,
    rebate_code_counter integer NOT NULL,
    parts_type_boundary_from integer,
    parts_type_boundary_until integer,
    rebate_percent numeric(9,5),
    description character varying(50)
);



CREATE TABLE public.parts_rebate_codes_sell (
    rebate_group_code integer NOT NULL,
    rebate_code character varying(5) NOT NULL,
    rebate_code_counter integer NOT NULL,
    parts_type_boundary_from integer,
    parts_type_boundary_until integer,
    rebate_percent numeric(9,5),
    description character varying(50)
);



CREATE TABLE public.parts_rebate_groups_buy (
    code integer NOT NULL,
    description character varying(25),
    CONSTRAINT parts_rebate_groups_buy_code_check CHECK ((code > 0))
);



CREATE TABLE public.parts_rebate_groups_sell (
    code integer NOT NULL,
    description character varying(25),
    CONSTRAINT parts_rebate_groups_sell_code_check CHECK ((code > 0))
);



CREATE TABLE public.parts_special_offer_prices (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    is_active boolean,
    valid_from_date date,
    valid_until_date date,
    price numeric(9,2),
    addition_percent numeric(9,5)
);



CREATE TABLE public.parts_special_prices (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    order_classification_flag character varying(2) NOT NULL,
    is_active boolean,
    price numeric(9,2),
    addition_percent numeric(9,5)
);



CREATE TABLE public.parts_stock (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    stock_no integer NOT NULL,
    storage_location_1 character varying(8),
    storage_location_2 character varying(8),
    usage_value numeric(9,2),
    stock_level numeric(8,2),
    stock_allocated numeric(8,2),
    minimum_stock_level numeric(8,2),
    has_warn_on_below_min_level boolean,
    maximum_stock_level integer,
    stop_order_flag character varying(1),
    revenue_account_group character varying(4),
    average_sales_statstic numeric(5,2),
    sales_current_year numeric(8,2),
    sales_previous_year numeric(8,2),
    total_buy_value numeric(9,2),
    total_sell_value numeric(9,2),
    provider_flag character varying(1),
    last_outflow_date date,
    last_inflow_date date,
    unevaluated_inflow_positions integer,
    is_disabled_in_parts_platforms boolean,
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10)
);



CREATE TABLE public.parts_supplier_numbers (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    external_number character varying(20)
);



CREATE TABLE public.parts_to_vehicles (
    part_number character varying(20) NOT NULL COLLATE pg_catalog."C",
    unique_reference character varying(20) NOT NULL,
    unique_counter integer NOT NULL,
    note character varying(20),
    vin_pattern character varying(17),
    model_pattern character varying(20),
    model_date_start date,
    model_date_end date
);



CREATE TABLE public.privacy_channels (
    channel_code character(1) NOT NULL,
    is_business boolean,
    description character varying(200)
);



CREATE TABLE public.privacy_details (
    subsidiary_to_company_ref integer NOT NULL,
    internal_id bigint NOT NULL,
    scope_code character(1) NOT NULL,
    channel_code character(1) NOT NULL
);



CREATE TABLE public.privacy_protection_consent (
    subsidiary_to_company_ref integer NOT NULL,
    internal_id bigint NOT NULL,
    customer_number integer,
    make_name character varying(9),
    validity_date_start date,
    validity_date_end date,
    created_timestamp timestamp without time zone,
    created_employee_no integer,
    last_change_timestamp timestamp without time zone,
    last_change_employee_no integer,
    first_ackno_timestamp timestamp without time zone,
    first_ackno_employee_no integer,
    last_ackno_timestamp timestamp without time zone,
    last_ackno_employee_no integer,
    first_consent_timestamp timestamp without time zone,
    first_consent_employee_no integer,
    last_consent_timestamp timestamp without time zone,
    last_consent_employee_no integer
);



CREATE TABLE public.privacy_scopes (
    scope_code character(1) NOT NULL,
    description character varying(200)
);



CREATE TABLE public.salutations (
    code character varying(2) NOT NULL,
    main_salutation character varying(20),
    title character varying(86),
    salutation_in_forms character varying(86),
    receiver_salutation character varying(86),
    full_salutation character varying(86),
    multiline_line_1 character varying(86),
    multiline_line_2 character varying(86)
);



CREATE TABLE public.subsidiaries (
    subsidiary integer NOT NULL,
    description character varying(42),
    subsidiary_to_company_ref integer
);



CREATE TABLE public.time_types (
    type integer NOT NULL,
    description character varying(50)
);



CREATE VIEW public.times AS
( WITH come_go AS (
         SELECT row_number() OVER wnd1 AS numeration,
            times.is_historic,
            times.employee_number,
            times.start_time,
            times.order_number,
            times.internal_record_ref,
            times.order_position,
            times.order_position_line,
            times.end_time,
            times.type,
            times.comment,
            times.principal_comment,
            times.is_pause_in_or_out,
            times.estimated_remaining_minutes,
            times.work_done,
            times.work_minutes,
            times.work_remaining_minutes,
            times.work_moved_order_position,
            times.work_moved_order_position_line,
            times.work_internal_error_flag
           FROM private.times
          WHERE (times.type = ANY (ARRAY[3, 4]))
          WINDOW wnd1 AS (PARTITION BY times.employee_number, times.type ORDER BY times.employee_number, times.start_time, times.type)
        ), grp AS (
         SELECT lead(come_go.start_time, 1) OVER wnd2 AS leave_time,
            (lead(come_go.start_time, 1) OVER wnd2 - come_go.start_time) AS duration,
            come_go.numeration,
            come_go.is_historic,
            come_go.employee_number,
            come_go.start_time,
            come_go.order_number,
            come_go.internal_record_ref,
            come_go.order_position,
            come_go.order_position_line,
            come_go.end_time,
            come_go.type,
            come_go.comment,
            come_go.principal_comment,
            come_go.is_pause_in_or_out,
            come_go.estimated_remaining_minutes,
            come_go.work_done,
            come_go.work_minutes,
            come_go.work_remaining_minutes,
            come_go.work_moved_order_position,
            come_go.work_moved_order_position_line,
            come_go.work_internal_error_flag
           FROM come_go
          WINDOW wnd2 AS (PARTITION BY come_go.numeration, come_go.employee_number ORDER BY come_go.employee_number, come_go.start_time, come_go.type)
        )
 SELECT grp.employee_number,
    grp.order_number,
    grp.start_time,
    1 AS type,
    NULL::text AS order_positions,
    NULL::integer AS order_position,
    NULL::integer AS order_position_line,
    grp.leave_time AS end_time,
    ((EXTRACT(epoch FROM grp.duration))::integer / 60) AS duration_minutes,
    (EXTRACT(epoch FROM grp.duration))::integer AS exact_duration_seconds,
    grp.duration,
    grp.is_historic
   FROM grp
  WHERE (grp.leave_time IS NOT NULL))
UNION
 SELECT times.employee_number,
    times.order_number,
    times.start_time,
    times.type,
    rtrim(translate(lpad((times.internal_record_ref)::text, 9, '0'::text), '01'::text, ' X'::text)) AS order_positions,
    times.order_position,
    times.order_position_line,
    times.end_time,
    ((EXTRACT(epoch FROM (times.end_time - times.start_time)))::integer / 60) AS duration_minutes,
    (EXTRACT(epoch FROM (times.end_time - times.start_time)))::integer AS exact_duration_seconds,
    (times.end_time - times.start_time) AS duration,
    times.is_historic
   FROM private.times
  WHERE (times.type = 2)
  ORDER BY 1, 3, 4, 2, 6, 7;



CREATE TABLE public.tire_storage (
    case_number integer NOT NULL,
    customer_number integer,
    vehicle_number integer,
    order_number integer,
    is_historic boolean,
    is_planned boolean,
    start_date date,
    scheduled_end_date date,
    note character varying(120),
    stock_no integer,
    date_of_removal date,
    removal_employee_no integer,
    price numeric(9,2),
    pressure_front numeric(4,2),
    pressure_rear numeric(4,2),
    torque integer
);



CREATE TABLE public.tire_storage_accessories (
    case_number integer NOT NULL,
    internal_counter integer NOT NULL,
    employee_no integer,
    manufacturer character varying(40),
    description_1 character varying(40),
    description_2 character varying(40),
    description_3 character varying(40),
    bin_location character varying(10),
    product_type character varying(5),
    manufacturer_code character varying(20),
    main_position character varying(2),
    sub_position character varying(2),
    note character varying(80),
    space_requirement integer,
    malfunction_date date,
    malfunction_employee integer,
    renewal_date date,
    renewal_employee integer,
    removal_state character varying(1)
);



CREATE TABLE public.tire_storage_wheels (
    case_number integer NOT NULL,
    internal_counter integer NOT NULL,
    employee_no integer,
    manufacturer character varying(40),
    product_name character varying(40),
    tire_dimension character varying(40),
    rim_description character varying(40),
    bin_location character varying(10),
    product_type character varying(5),
    note character varying(80),
    manufacturer_code character varying(20),
    wheel_position character varying(2),
    tire_tread_depth numeric(4,2),
    rim_nuts_included boolean,
    wheel_cover_included boolean,
    is_runflat boolean,
    is_uhp boolean,
    has_rdks boolean,
    rdks_code character varying(12),
    space_requirement integer,
    malfunction_date date,
    malfunction_employee integer,
    renewal_date date,
    renewal_employee integer,
    removal_state character varying(1)
);



CREATE TABLE public.transit_customers (
    order_number integer NOT NULL,
    order_position integer NOT NULL,
    order_position_line integer NOT NULL,
    first_name character varying(45),
    family_name character varying(45),
    salutation_code character varying(2),
    country character varying(3),
    zip_code character varying(20),
    home_city character varying(25),
    home_street character varying(27),
    phone_number character varying(15),
    fullname_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (((first_name)::text || ' '::text) || (family_name)::text))) STORED
);



CREATE TABLE public.transit_vehicles (
    order_number integer NOT NULL,
    order_position integer NOT NULL,
    order_position_line integer NOT NULL,
    make_number integer,
    make_text character varying(10),
    model_code character varying(16),
    model_text character varying(18),
    color_text character varying(15),
    license_plate character varying(12),
    vin character varying(17),
    first_registration_date date,
    model_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (model_text)::text)) STORED
);



CREATE TABLE public.vat_keys (
    subsidiary_to_company_ref bigint NOT NULL,
    vat_key text NOT NULL,
    key_validity_date date,
    branch bigint,
    description text,
    vat_rate bigint,
    create_date date,
    vat_account bigint,
    advanced_turnover_tax_pos bigint
);



CREATE TABLE public.vehicle_bodys (
    code character varying(2) NOT NULL,
    description character varying(200),
    CONSTRAINT vehicle_bodys_code_check CHECK (((code)::text > ''::text))
);



CREATE TABLE public.vehicle_buy_types (
    code character varying(1) NOT NULL,
    description character varying(40)
);



CREATE TABLE public.vehicle_contact_log_pemissions (
    vehicle_number integer NOT NULL,
    case_number integer NOT NULL,
    employee_no integer NOT NULL
);



CREATE TABLE public.vehicle_pre_owned_codes (
    code character varying(1) NOT NULL,
    description character varying(40)
);



CREATE TABLE public.vehicle_sale_types (
    code character varying(1) NOT NULL,
    description character varying(40)
);



CREATE VIEW public.vehicle_top_note AS
 SELECT vehicle_number,
    string_agg(text, ' '::text) AS text
   FROM private.vehicle_contact_log
  GROUP BY vehicle_number, case_number
 HAVING (case_number = 0)
  ORDER BY vehicle_number, case_number;



CREATE TABLE public.vehicle_types (
    code character varying(1) NOT NULL,
    is_new_or_similar boolean,
    description character varying(40)
);



CREATE TABLE public.vehicles (
    internal_number integer NOT NULL,
    vin character varying(17),
    license_plate character varying(12),
    license_plate_country character varying(3),
    license_plate_season character varying(6),
    make_number integer,
    free_form_make_text character varying(10),
    model_code character varying(25),
    free_form_model_text character varying(40),
    is_roadworthy boolean,
    is_customer_vehicle boolean,
    dealer_vehicle_type character varying(1),
    dealer_vehicle_number integer,
    first_registration_date date,
    readmission_date date,
    next_service_date date,
    next_service_km integer,
    next_service_miles integer,
    production_year numeric(4,0),
    owner_number integer,
    holder_number integer,
    previous_owner_number integer,
    previous_owner_counter integer,
    last_holder_change_date date,
    german_kba_hsn character varying(4),
    german_kba_tsn character varying(15),
    austria_nat_code character varying(15),
    is_prefer_km boolean,
    mileage_km integer,
    mileage_miles integer,
    odometer_reading_date date,
    engine_number character varying(20),
    gear_number character varying(20),
    unloaded_weight integer,
    gross_vehicle_weight integer,
    power_kw integer,
    cubic_capacity integer,
    is_all_accidents_repaired boolean,
    accidents_counter integer,
    has_tyre_pressure_sensor boolean,
    carkey_number character varying(15),
    internal_source_flag character varying(3),
    emission_code character varying(4),
    first_sold_country character varying(3),
    first_sold_dealer_code integer,
    body_paint_code character varying(20),
    body_paint_description character varying(40),
    is_body_paint_metallic boolean,
    interior_paint_code character varying(20),
    interior_paint_description character varying(40),
    trim_code character varying(20),
    trim_description character varying(40),
    fine_dust_label character varying(1),
    internal_assignment character varying(10),
    ricambi_free_input character varying(20),
    document_number character varying(10),
    salesman_number integer,
    sale_date date,
    next_emission_test_date date,
    next_general_inspection_date date,
    next_rust_inspection_date date,
    next_exceptional_inspection_da date,
    last_change_date date,
    last_change_employee_no integer,
    created_date date,
    created_employee_no integer,
    subsidiary integer,
    last_change_subsidiary integer,
    other_date_1 date,
    other_date_2 date,
    lock_by_workstation integer,
    lock_time timestamp without time zone,
    lock_trace character varying(100),
    lock_trigger character varying(100),
    lock_by_employee integer,
    lock_sourcecode character varying(200),
    lock_machine character varying(18),
    lock_task integer,
    lock_service_name character varying(10),
    free_form_model_text_vector tsvector GENERATED ALWAYS AS (to_tsvector('german'::regconfig, (free_form_model_text)::text)) STORED,
    CONSTRAINT vehicles_check CHECK (((owner_number > 0) OR (holder_number > 0) OR (owner_number = '-1000000000'::integer)))
);



CREATE VIEW public.view_invoices AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    sum(i.job_amount_net) AS labour_amount,
    sum(i.job_rebate) AS labour_rebate_amount,
    sum(i.part_amount_net) AS part_amount,
    sum(i.part_rebate) AS part_rebate_amount,
    count(*) AS invoice_count,
    sum(i.total_net) AS overall,
    v.make_number
   FROM ((public.invoices i
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((i.invoice_type < 7) AND (i.invoice_type <> 5) AND (i.cancelation_date IS NULL))
  GROUP BY i.invoice_date, i.subsidiary, v.make_number;



CREATE VIEW public.view_invoices_cash AS
 SELECT invoice_date,
    subsidiary,
    date_part('day'::text, invoice_date) AS day,
    date_part('month'::text, invoice_date) AS month,
    date_part('year'::text, invoice_date) AS year,
    date_part('week'::text, invoice_date) AS week,
    sum(total_net) AS overall
   FROM public.invoices i
  WHERE ((invoice_type = 5) AND (cancelation_date IS NULL))
  GROUP BY invoice_date, subsidiary
  ORDER BY invoice_date;



CREATE VIEW public.view_labours_external AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    l.charge_type AS type,
    sum(l.net_price_in_order) AS overall,
    v.make_number
   FROM (((public.labours l
     JOIN public.invoices i ON (((i.invoice_number = l.invoice_number) AND (i.invoice_type = l.invoice_type))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((l.invoice_type < 7) AND (l.invoice_type <> 5) AND (i.cancelation_date IS NULL) AND (((l.charge_type >= 90) AND (l.charge_type <= 99)) OR ((l.charge_type >= 900) AND (l.charge_type <= 999))))
  GROUP BY i.invoice_date, l.charge_type, i.subsidiary, v.make_number
  ORDER BY i.invoice_date;



CREATE VIEW public.view_labours_goodwill AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    l.charge_type AS type,
    round(((sum(l.net_price_in_order) * ((100)::numeric - l.goodwill_percent)) / (100)::numeric), 2) AS overall,
    v.make_number
   FROM (((public.labours l
     JOIN public.invoices i ON (((i.invoice_number = l.invoice_number) AND (i.invoice_type = l.invoice_type))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((l.invoice_type < 7) AND (l.invoice_type <> 5) AND (i.cancelation_date IS NULL) AND (((l.labour_type)::text = 'K'::text) OR ((l.labour_type)::text = 'k'::text) OR ((l.labour_type)::text = 'Ik'::text) OR ((l.labour_type)::text = 'S'::text) OR ((l.labour_type)::text = 's'::text) OR ((l.labour_type)::text = 'Is'::text)))
  GROUP BY i.invoice_date, l.goodwill_percent, l.charge_type, i.subsidiary, v.make_number
  ORDER BY i.invoice_date;



CREATE VIEW public.view_labours_rebate AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    l.charge_type AS type,
        CASE
            WHEN ((l.rebate_percent > (0)::numeric) AND (l.rebate_percent < (100)::numeric)) THEN round((((sum(l.net_price_in_order) * (100)::numeric) / ((100)::numeric - l.rebate_percent)) - sum(l.net_price_in_order)), 2)
            WHEN (l.rebate_percent = (0)::numeric) THEN 0.00
            ELSE l.net_price_in_order
        END AS overall,
    v.make_number
   FROM (((public.labours l
     JOIN public.invoices i ON (((i.invoice_number = l.invoice_number) AND (i.invoice_type = l.invoice_type))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((l.invoice_type < 7) AND (l.invoice_type <> 5) AND (i.cancelation_date IS NULL))
  GROUP BY i.invoice_date, l.rebate_percent, l.charge_type, i.subsidiary, v.make_number, l.net_price_in_order
  ORDER BY i.invoice_date;



CREATE VIEW public.view_labours_usagevalue AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    l.charge_type AS type,
        CASE
            WHEN (sum(l.usage_value) IS NOT NULL) THEN sum(l.usage_value)
            ELSE 0.00
        END AS overall,
    v.make_number
   FROM (((public.labours l
     JOIN public.invoices i ON (((i.invoice_number = l.invoice_number) AND (i.invoice_type = l.invoice_type))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((l.invoice_type < 7) AND (l.invoice_type <> 5) AND (i.cancelation_date IS NULL))
  GROUP BY i.invoice_date, l.charge_type, i.subsidiary, v.make_number
  ORDER BY i.invoice_date;



CREATE VIEW public.view_parts_goodwill AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    p.parts_type AS type,
    round(((sum(p.sum) * ((100)::numeric - p.goodwill_percent)) / (100)::numeric), 2) AS overall,
    v.make_number
   FROM ((((public.parts p
     JOIN public.invoices i ON (((i.invoice_number = p.invoice_number) AND (i.invoice_type = p.invoice_type))))
     JOIN public.labours l ON (((p.order_number = l.order_number) AND (p.order_position = l.order_position))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((p.invoice_type < 7) AND (p.invoice_type <> 5) AND (i.cancelation_date IS NULL) AND (((l.labour_type)::text = 'K'::text) OR ((l.labour_type)::text = 'k'::text) OR ((l.labour_type)::text = 'Ik'::text) OR ((l.labour_type)::text = 'S'::text) OR ((l.labour_type)::text = 's'::text) OR ((l.labour_type)::text = 'Is'::text)))
  GROUP BY i.invoice_date, p.goodwill_percent, p.parts_type, i.subsidiary, v.make_number
  ORDER BY i.invoice_date;



CREATE VIEW public.view_parts_rebate AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    p.parts_type AS type,
        CASE
            WHEN ((p.rebate_percent > (0)::numeric) AND (p.rebate_percent < (100)::numeric)) THEN round((((sum(p.sum) * (100)::numeric) / ((100)::numeric - p.rebate_percent)) - sum(p.sum)), 2)
            WHEN (p.rebate_percent = (0)::numeric) THEN sum(p.sum)
            ELSE 0.00
        END AS overall,
    v.make_number
   FROM (((public.parts p
     JOIN public.invoices i ON (((i.invoice_number = p.invoice_number) AND (i.invoice_type = p.invoice_type))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((p.invoice_type < 7) AND (p.invoice_type <> 5) AND (i.cancelation_date IS NULL))
  GROUP BY i.invoice_date, p.rebate_percent, p.parts_type, i.subsidiary, v.make_number
  ORDER BY i.invoice_date;



CREATE VIEW public.view_parts_usagevalue AS
 SELECT i.invoice_date,
    i.subsidiary,
    date_part('day'::text, i.invoice_date) AS day,
    date_part('month'::text, i.invoice_date) AS month,
    date_part('year'::text, i.invoice_date) AS year,
    date_part('week'::text, i.invoice_date) AS week,
    p.parts_type AS type,
        CASE
            WHEN (sum(p.usage_value) IS NOT NULL) THEN sum(p.usage_value)
            ELSE 0.00
        END AS overall,
    v.make_number
   FROM (((public.parts p
     JOIN public.invoices i ON (((i.invoice_number = p.invoice_number) AND (i.invoice_type = p.invoice_type))))
     JOIN public.orders o ON ((o.number = i.order_number)))
     LEFT JOIN public.vehicles v ON ((v.internal_number = o.vehicle_number)))
  WHERE ((p.invoice_type < 7) AND (p.invoice_type <> 5) AND (i.cancelation_date IS NULL))
  GROUP BY i.invoice_date, p.parts_type, i.subsidiary, v.make_number
  ORDER BY i.invoice_date;



CREATE TABLE public.wtp_pickup_bring_type (
    type integer NOT NULL,
    description character varying(100)
);



CREATE TABLE public.wtp_progress_status (
    code integer NOT NULL,
    description character varying(50)
);



CREATE TABLE public.wtp_urgency (
    code integer NOT NULL,
    description character varying(50)
);



CREATE TABLE public.wtp_vehicle_status (
    code integer NOT NULL,
    description character varying(50)
);



CREATE TABLE public.year_calendar (
    calendar_id integer NOT NULL,
    date date NOT NULL,
    day_off_declaration integer,
    is_school_holid boolean,
    is_public_holid boolean,
    day_note character varying(20)
);



CREATE TABLE public.year_calendar_day_off_codes (
    code integer NOT NULL,
    description character varying(50)
);



CREATE TABLE public.year_calendar_subsidiary_mapping (
    subsidiary integer NOT NULL,
    year integer NOT NULL,
    calendar_id integer
);



ALTER TABLE ONLY public.financing_examples ALTER COLUMN id SET DEFAULT nextval('public.financing_examples_id_seq'::regclass);



ALTER TABLE ONLY public.leasing_examples ALTER COLUMN id SET DEFAULT nextval('public.leasing_examples_id_seq'::regclass);



ALTER TABLE ONLY public.absence_calendar
    ADD CONSTRAINT absence_calendar_pkey PRIMARY KEY (employee_number, date, unique_dummy);



ALTER TABLE ONLY public.absence_reasons
    ADD CONSTRAINT absence_reasons_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.absence_types
    ADD CONSTRAINT absence_types_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.accounts_characteristics
    ADD CONSTRAINT accounts_characteristics_pkey PRIMARY KEY (subsidiary_to_company_ref, skr51_branch, skr51_make, skr51_cost_center, skr51_sales_channel, skr51_cost_unit);



ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.appointments_text
    ADD CONSTRAINT appointments_text_pkey PRIMARY KEY (appointment_id);



ALTER TABLE ONLY public.charge_type_descriptions
    ADD CONSTRAINT charge_type_descriptions_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.charge_types
    ADD CONSTRAINT charge_types_pkey PRIMARY KEY (type, subsidiary);



ALTER TABLE ONLY public.clearing_delay_types
    ADD CONSTRAINT clearing_delay_types_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.codes_customer_def
    ADD CONSTRAINT codes_customer_def_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.codes_customer_list
    ADD CONSTRAINT codes_customer_list_pkey PRIMARY KEY (customer_number, code);



ALTER TABLE ONLY public.codes_vehicle_date_def
    ADD CONSTRAINT codes_vehicle_date_def_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.codes_vehicle_date
    ADD CONSTRAINT codes_vehicle_date_pkey PRIMARY KEY (vehicle_number, code);



ALTER TABLE ONLY public.codes_vehicle_def
    ADD CONSTRAINT codes_vehicle_def_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.codes_vehicle_list
    ADD CONSTRAINT codes_vehicle_list_pkey PRIMARY KEY (vehicle_number, code);



ALTER TABLE ONLY public.codes_vehicle_mileage_def
    ADD CONSTRAINT codes_vehicle_mileage_def_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.codes_vehicle_mileage
    ADD CONSTRAINT codes_vehicle_mileage_pkey PRIMARY KEY (vehicle_number, code);



ALTER TABLE ONLY public.com_number_types
    ADD CONSTRAINT com_number_types_pkey PRIMARY KEY (typ);



ALTER TABLE ONLY public.configuration_numeric
    ADD CONSTRAINT configuration_numeric_pkey PRIMARY KEY (parameter_number, subsidiary);



ALTER TABLE ONLY public.configuration
    ADD CONSTRAINT configuration_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.customer_codes
    ADD CONSTRAINT customer_codes_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.customer_com_numbers
    ADD CONSTRAINT customer_com_numbers_customer_number_com_type_search_addres_key UNIQUE (customer_number, com_type, search_address);



ALTER TABLE ONLY public.customer_com_numbers
    ADD CONSTRAINT customer_com_numbers_pkey PRIMARY KEY (customer_number, counter);



ALTER TABLE ONLY public.customer_contact_log_pemissions
    ADD CONSTRAINT customer_contact_log_pemissions_pkey PRIMARY KEY (customer_number, case_number, employee_no);



ALTER TABLE ONLY public.customer_profession_codes
    ADD CONSTRAINT customer_profession_codes_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.customer_supplier_bank_information
    ADD CONSTRAINT customer_supplier_bank_information_pkey PRIMARY KEY (customer_number);



ALTER TABLE ONLY public.customer_to_customercodes
    ADD CONSTRAINT customer_to_customercodes_pkey PRIMARY KEY (customer_number, customer_code);



ALTER TABLE ONLY public.customer_to_professioncodes
    ADD CONSTRAINT customer_to_professioncodes_pkey PRIMARY KEY (customer_number, profession_code);



ALTER TABLE ONLY public.customers_suppliers
    ADD CONSTRAINT customers_suppliers_pkey PRIMARY KEY (customer_number);



ALTER TABLE ONLY public.dealer_sales_aid_bonus
    ADD CONSTRAINT dealer_sales_aid_bonus_pkey PRIMARY KEY (dealer_vehicle_type, dealer_vehicle_number, code, note);



ALTER TABLE ONLY public.dealer_sales_aid
    ADD CONSTRAINT dealer_sales_aid_pkey PRIMARY KEY (dealer_vehicle_type, dealer_vehicle_number, code, note);



ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_pkey PRIMARY KEY (dealer_vehicle_type, dealer_vehicle_number);



ALTER TABLE ONLY public.document_types
    ADD CONSTRAINT document_types_pkey PRIMARY KEY (document_type_in_journal);



ALTER TABLE ONLY public.employees_breaktimes
    ADD CONSTRAINT employees_breaktimes_pkey PRIMARY KEY (employee_number, validity_date, dayofweek, break_start);



ALTER TABLE ONLY public.employees_group_mapping
    ADD CONSTRAINT employees_group_mapping_pkey PRIMARY KEY (employee_number, validity_date, grp_code);



ALTER TABLE ONLY public.employees_history
    ADD CONSTRAINT employees_history_pkey PRIMARY KEY (employee_number, validity_date);



ALTER TABLE ONLY public.employees_worktimes
    ADD CONSTRAINT employees_worktimes_pkey PRIMARY KEY (employee_number, validity_date, dayofweek);



ALTER TABLE ONLY public.external_customer_references
    ADD CONSTRAINT external_customer_references_pkey PRIMARY KEY (api_type, api_id, customer_number, subsidiary);



ALTER TABLE ONLY public.external_reference_parties
    ADD CONSTRAINT external_reference_parties_pkey PRIMARY KEY (api_type, api_id);



ALTER TABLE ONLY public.financing_examples
    ADD CONSTRAINT financing_examples_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.financing_examples
    ADD CONSTRAINT financing_examples_source_referenced_dealer_vehicle_type_re_key UNIQUE (source, referenced_dealer_vehicle_type, referenced_dealer_vehicle_no);



ALTER TABLE ONLY public.fuels
    ADD CONSTRAINT fuels_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.invoice_types
    ADD CONSTRAINT invoice_types_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (invoice_type, invoice_number);



ALTER TABLE ONLY public.journal_accountings
    ADD CONSTRAINT journal_accountings_pkey PRIMARY KEY (subsidiary_to_company_ref, accounting_date, document_type, document_number, position_in_document);



ALTER TABLE ONLY public.labour_types
    ADD CONSTRAINT labour_types_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.labours_groups
    ADD CONSTRAINT labours_groups_pkey PRIMARY KEY (source_number, labour_number_range);



ALTER TABLE ONLY public.labours_master
    ADD CONSTRAINT labours_master_pkey PRIMARY KEY (source_number, labour_number, mapping_code);



ALTER TABLE ONLY public.labours
    ADD CONSTRAINT labours_pkey PRIMARY KEY (order_number, order_position, order_position_line);



ALTER TABLE ONLY public.leasing_examples
    ADD CONSTRAINT leasing_examples_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.leasing_examples
    ADD CONSTRAINT leasing_examples_source_referenced_dealer_vehicle_type_refe_key UNIQUE (source, referenced_dealer_vehicle_type, referenced_dealer_vehicle_no);



ALTER TABLE ONLY public.makes
    ADD CONSTRAINT makes_pkey PRIMARY KEY (make_number);



ALTER TABLE ONLY public.model_to_fuels
    ADD CONSTRAINT model_to_fuels_pkey PRIMARY KEY (make_number, model_code, code);



ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_pkey PRIMARY KEY (make_number, model_code);



ALTER TABLE ONLY public.nominal_accounts
    ADD CONSTRAINT nominal_accounts_pkey PRIMARY KEY (subsidiary_to_company_ref, nominal_account_number);



ALTER TABLE ONLY public.order_classifications_def
    ADD CONSTRAINT order_classifications_def_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (number);



ALTER TABLE ONLY public.part_types
    ADD CONSTRAINT part_types_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.parts_additional_descriptions
    ADD CONSTRAINT parts_additional_descriptions_pkey PRIMARY KEY (part_number);



ALTER TABLE ONLY public.parts_inbound_delivery_notes
    ADD CONSTRAINT parts_inbound_delivery_notes_pkey PRIMARY KEY (supplier_number, year_key, number_main, number_sub, counter);



ALTER TABLE ONLY public.parts_master
    ADD CONSTRAINT parts_master_pkey PRIMARY KEY (part_number);



ALTER TABLE ONLY public.parts
    ADD CONSTRAINT parts_pkey PRIMARY KEY (order_number, order_position, order_position_line);



ALTER TABLE ONLY public.parts_rebate_codes_buy
    ADD CONSTRAINT parts_rebate_codes_buy_pkey PRIMARY KEY (rebate_group_code, rebate_code, rebate_code_counter);



ALTER TABLE ONLY public.parts_rebate_codes_sell
    ADD CONSTRAINT parts_rebate_codes_sell_pkey PRIMARY KEY (rebate_group_code, rebate_code, rebate_code_counter);



ALTER TABLE ONLY public.parts_rebate_groups_buy
    ADD CONSTRAINT parts_rebate_groups_buy_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.parts_rebate_groups_sell
    ADD CONSTRAINT parts_rebate_groups_sell_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.parts_special_offer_prices
    ADD CONSTRAINT parts_special_offer_prices_pkey PRIMARY KEY (part_number);



ALTER TABLE ONLY public.parts_special_prices
    ADD CONSTRAINT parts_special_prices_pkey PRIMARY KEY (part_number, order_classification_flag);



ALTER TABLE ONLY public.parts_stock
    ADD CONSTRAINT parts_stock_pkey PRIMARY KEY (part_number, stock_no);



ALTER TABLE ONLY public.parts_supplier_numbers
    ADD CONSTRAINT parts_supplier_numbers_pkey PRIMARY KEY (part_number);



ALTER TABLE ONLY public.parts_to_vehicles
    ADD CONSTRAINT parts_to_vehicles_pkey PRIMARY KEY (part_number, unique_reference, unique_counter);



ALTER TABLE ONLY public.privacy_channels
    ADD CONSTRAINT privacy_channels_pkey PRIMARY KEY (channel_code);



ALTER TABLE ONLY public.privacy_details
    ADD CONSTRAINT privacy_details_pkey PRIMARY KEY (subsidiary_to_company_ref, internal_id, scope_code, channel_code);



ALTER TABLE ONLY public.privacy_protection_consent
    ADD CONSTRAINT privacy_protection_consent_pkey PRIMARY KEY (subsidiary_to_company_ref, internal_id);



ALTER TABLE ONLY public.privacy_scopes
    ADD CONSTRAINT privacy_scopes_pkey PRIMARY KEY (scope_code);



ALTER TABLE ONLY public.salutations
    ADD CONSTRAINT salutations_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.subsidiaries
    ADD CONSTRAINT subsidiaries_pkey PRIMARY KEY (subsidiary);



ALTER TABLE ONLY public.time_types
    ADD CONSTRAINT time_types_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.tire_storage_accessories
    ADD CONSTRAINT tire_storage_accessories_pkey PRIMARY KEY (case_number, internal_counter);



ALTER TABLE ONLY public.tire_storage
    ADD CONSTRAINT tire_storage_pkey PRIMARY KEY (case_number);



ALTER TABLE ONLY public.tire_storage_wheels
    ADD CONSTRAINT tire_storage_wheels_pkey PRIMARY KEY (case_number, internal_counter);



ALTER TABLE ONLY public.transit_customers
    ADD CONSTRAINT transit_customers_pkey PRIMARY KEY (order_number, order_position, order_position_line);



ALTER TABLE ONLY public.transit_vehicles
    ADD CONSTRAINT transit_vehicles_pkey PRIMARY KEY (order_number, order_position, order_position_line);



ALTER TABLE ONLY public.vat_keys
    ADD CONSTRAINT vat_keys_pkey PRIMARY KEY (subsidiary_to_company_ref, vat_key);



ALTER TABLE ONLY public.vehicle_bodys
    ADD CONSTRAINT vehicle_bodys_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.vehicle_buy_types
    ADD CONSTRAINT vehicle_buy_types_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.vehicle_contact_log_pemissions
    ADD CONSTRAINT vehicle_contact_log_pemissions_pkey PRIMARY KEY (vehicle_number, case_number, employee_no);



ALTER TABLE ONLY public.vehicle_pre_owned_codes
    ADD CONSTRAINT vehicle_pre_owned_codes_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.vehicle_sale_types
    ADD CONSTRAINT vehicle_sale_types_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.vehicle_types
    ADD CONSTRAINT vehicle_types_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.vehicles
    ADD CONSTRAINT vehicles_pkey PRIMARY KEY (internal_number);



ALTER TABLE ONLY public.wtp_pickup_bring_type
    ADD CONSTRAINT wtp_pickup_bring_type_pkey PRIMARY KEY (type);



ALTER TABLE ONLY public.wtp_progress_status
    ADD CONSTRAINT wtp_progress_status_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.wtp_urgency
    ADD CONSTRAINT wtp_urgency_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.wtp_vehicle_status
    ADD CONSTRAINT wtp_vehicle_status_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.year_calendar_day_off_codes
    ADD CONSTRAINT year_calendar_day_off_codes_pkey PRIMARY KEY (code);



ALTER TABLE ONLY public.year_calendar
    ADD CONSTRAINT year_calendar_pkey PRIMARY KEY (calendar_id, date);



ALTER TABLE ONLY public.year_calendar_subsidiary_mapping
    ADD CONSTRAINT year_calendar_subsidiary_mapping_pkey PRIMARY KEY (subsidiary, year);



CREATE INDEX appointments_bring_timestamp_idx ON public.appointments USING btree (bring_timestamp);



CREATE INDEX appointments_btrim_idx ON public.appointments USING btree (TRIM(BOTH FROM replace((pseudo_license_plate)::text, '-'::text, ' '::text)) COLLATE "C");



CREATE INDEX appointments_created_timestamp_idx ON public.appointments USING btree (created_timestamp);



CREATE INDEX appointments_lower_idx ON public.appointments USING btree (lower((pseudo_customer_name)::text));



CREATE INDEX appointments_lower_idx1 ON public.appointments USING btree (lower((pseudo_model_text)::text));



CREATE INDEX appointments_return_timestamp_idx ON public.appointments USING btree (return_timestamp);



CREATE INDEX appointments_to_tsvector_idx ON public.appointments USING btree (to_tsvector('german'::regconfig, (pseudo_customer_name)::text));



CREATE INDEX appointments_to_tsvector_idx1 ON public.appointments USING btree (to_tsvector('german'::regconfig, (pseudo_model_text)::text));



CREATE INDEX customer_com_numbers_com_type_idx ON public.customer_com_numbers USING btree (com_type);



CREATE INDEX customer_com_numbers_is_reference_idx ON public.customer_com_numbers USING btree (is_reference);



CREATE INDEX customer_com_numbers_lower_idx ON public.customer_com_numbers USING btree (lower((contact_lastname)::text));



CREATE INDEX customer_com_numbers_lower_idx1 ON public.customer_com_numbers USING btree (lower((contact_firstname)::text));



CREATE INDEX customer_com_numbers_lower_idx2 ON public.customer_com_numbers USING btree (lower((((contact_firstname)::text || ' '::text) || (contact_lastname)::text)));



CREATE INDEX customer_com_numbers_lower_idx3 ON public.customer_com_numbers USING btree (lower((contact_description)::text));



CREATE INDEX customer_com_numbers_lower_idx4 ON public.customer_com_numbers USING btree (lower((note)::text));



CREATE INDEX customer_com_numbers_phone_number_idx ON public.customer_com_numbers USING btree (phone_number COLLATE "C");



CREATE INDEX customer_com_numbers_search_address_idx ON public.customer_com_numbers USING btree (search_address COLLATE "C");



CREATE INDEX customers_suppliers_contact_family_name_idx ON public.customers_suppliers USING btree (contact_family_name);



CREATE INDEX customers_suppliers_contact_first_name_idx ON public.customers_suppliers USING btree (contact_first_name);



CREATE INDEX customers_suppliers_family_name_idx ON public.customers_suppliers USING btree (family_name);



CREATE INDEX customers_suppliers_first_name_idx ON public.customers_suppliers USING btree (first_name);



CREATE INDEX customers_suppliers_lower_idx ON public.customers_suppliers USING btree (lower((name_prefix)::text));



CREATE INDEX customers_suppliers_lower_idx1 ON public.customers_suppliers USING btree (lower((((name_prefix)::text || ' '::text) || (name_postfix)::text)));



CREATE INDEX customers_suppliers_lower_idx10 ON public.customers_suppliers USING btree (lower((contact_first_name)::text));



CREATE INDEX customers_suppliers_lower_idx11 ON public.customers_suppliers USING btree (lower((((contact_first_name)::text || ' '::text) || (contact_family_name)::text)));



CREATE INDEX customers_suppliers_lower_idx2 ON public.customers_suppliers USING btree (lower((((first_name)::text || ' '::text) || (name_postfix)::text)));



CREATE INDEX customers_suppliers_lower_idx3 ON public.customers_suppliers USING btree (lower((((family_name)::text || ' '::text) || (name_postfix)::text)));



CREATE INDEX customers_suppliers_lower_idx4 ON public.customers_suppliers USING btree (lower((first_name)::text));



CREATE INDEX customers_suppliers_lower_idx5 ON public.customers_suppliers USING btree (lower((family_name)::text));



CREATE INDEX customers_suppliers_lower_idx6 ON public.customers_suppliers USING btree (lower((((first_name)::text || ' '::text) || (family_name)::text)));



CREATE INDEX customers_suppliers_lower_idx7 ON public.customers_suppliers USING btree (lower((((family_name)::text || ' '::text) || (first_name)::text)));



CREATE INDEX customers_suppliers_lower_idx8 ON public.customers_suppliers USING btree (lower((name_postfix)::text));



CREATE INDEX customers_suppliers_lower_idx9 ON public.customers_suppliers USING btree (lower((contact_family_name)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (name_prefix)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx1 ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (first_name)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx2 ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (family_name)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx3 ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (name_postfix)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx4 ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (home_street)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx5 ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (home_city)::text));



CREATE INDEX customers_suppliers_to_tsvector_idx6 ON public.customers_suppliers USING btree (to_tsvector('german'::regconfig, (((contact_first_name)::text || ' '::text) || (contact_family_name)::text)));



CREATE INDEX customers_suppliers_zip_code_idx ON public.customers_suppliers USING btree (zip_code);



CREATE INDEX dealer_vehicles_btrim_idx ON public.dealer_vehicles USING btree (TRIM(BOTH FROM replace((out_license_plate)::text, '-'::text, ' '::text)) COLLATE "C");



CREATE INDEX labours_groups_source_idx ON public.labours_groups USING btree (source);



CREATE INDEX labours_lower_idx ON public.labours USING btree (lower((text_line)::text));



CREATE INDEX labours_master_btrim_idx ON public.labours_master USING btree (TRIM(BOTH FROM labour_number));



CREATE INDEX labours_master_lower_idx ON public.labours_master USING btree (lower(text));



CREATE INDEX labours_master_source_idx ON public.labours_master USING btree (source);



CREATE INDEX labours_to_tsvector_idx ON public.labours USING btree (to_tsvector('german'::regconfig, (text_line)::text));



CREATE INDEX make_desc_vector_idx ON public.makes USING btree (to_tsvector('german'::regconfig, (description)::text));



CREATE INDEX makes_lower_idx ON public.makes USING btree (lower((description)::text));



CREATE INDEX models_lower_idx ON public.models USING btree (lower((description)::text));



CREATE INDEX parts_additional_descriptions_lower_idx ON public.parts_additional_descriptions USING btree (lower((description)::text));



CREATE INDEX parts_additional_descriptions_search_description_idx ON public.parts_additional_descriptions USING btree (search_description);



CREATE INDEX parts_lower_idx ON public.parts USING btree (lower((text_line)::text));



CREATE INDEX parts_master_lower_idx ON public.parts_master USING btree (lower((description)::text));



CREATE INDEX parts_master_search_description_idx ON public.parts_master USING btree (search_description);



CREATE INDEX parts_stock_lower_idx ON public.parts_stock USING btree (lower((storage_location_1)::text));



CREATE INDEX parts_stock_lower_idx1 ON public.parts_stock USING btree (lower((storage_location_2)::text));



CREATE INDEX parts_supplier_numbers_external_number_idx ON public.parts_supplier_numbers USING btree (external_number);



CREATE INDEX parts_to_tsvector_idx ON public.parts USING btree (to_tsvector('german'::regconfig, (text_line)::text));



CREATE INDEX parts_to_vehicles_model_date_end_idx ON public.parts_to_vehicles USING btree (model_date_end);



CREATE INDEX parts_to_vehicles_model_date_start_idx ON public.parts_to_vehicles USING btree (model_date_start);



CREATE INDEX parts_to_vehicles_model_pattern_idx ON public.parts_to_vehicles USING btree (model_pattern);



CREATE INDEX parts_to_vehicles_vin_pattern_idx ON public.parts_to_vehicles USING btree (vin_pattern);



CREATE INDEX transit_vehicles_btrim_idx ON public.transit_vehicles USING btree (TRIM(BOTH FROM replace((license_plate)::text, '-'::text, ' '::text)) COLLATE "C");



CREATE INDEX transit_vehicles_lower_idx ON public.transit_vehicles USING btree (lower((model_text)::text));



CREATE INDEX vehicles_btrim_idx ON public.vehicles USING btree (TRIM(BOTH FROM replace((license_plate)::text, '-'::text, ' '::text)) COLLATE "C");



CREATE INDEX vehicles_holder_number_idx ON public.vehicles USING btree (holder_number);



CREATE INDEX vehicles_license_plate_idx ON public.vehicles USING btree (license_plate COLLATE "C");



CREATE INDEX vehicles_lower_idx ON public.vehicles USING btree (lower((free_form_make_text)::text));



CREATE INDEX vehicles_lower_idx1 ON public.vehicles USING btree (lower((free_form_model_text)::text));



CREATE INDEX vehicles_owner_number_idx ON public.vehicles USING btree (owner_number);



CREATE INDEX vehicles_vin_idx ON public.vehicles USING btree (vin);



CREATE TRIGGER absence_calendar_modified_notify AFTER INSERT OR DELETE OR UPDATE ON public.absence_calendar FOR EACH ROW EXECUTE FUNCTION public.absence_calendar_modified();



CREATE TRIGGER app_customercodes_change_trigger AFTER INSERT OR DELETE OR UPDATE ON public.customer_codes FOR EACH STATEMENT EXECUTE FUNCTION public.track_table_changes();



CREATE TRIGGER app_customers_suppliers_change_trigger AFTER INSERT OR DELETE OR UPDATE ON public.customers_suppliers FOR EACH STATEMENT EXECUTE FUNCTION public.track_table_changes();



CREATE TRIGGER app_order_change_trigger AFTER INSERT OR DELETE OR UPDATE ON public.orders FOR EACH STATEMENT EXECUTE FUNCTION public.track_table_changes();



CREATE TRIGGER delete_customer_contact_log_permissions AFTER DELETE ON public.customer_contact_log_pemissions FOR EACH ROW EXECUTE FUNCTION public.customer_contact_log_pemissions_update();



CREATE TRIGGER delete_vehicle_contact_log_permissions AFTER DELETE ON public.vehicle_contact_log_pemissions FOR EACH ROW EXECUTE FUNCTION public.vehicle_contact_log_pemissions_update();



CREATE TRIGGER insert_customer_contact_log_permissions AFTER INSERT ON public.customer_contact_log_pemissions FOR EACH ROW EXECUTE FUNCTION public.customer_contact_log_pemissions_update();



CREATE TRIGGER insert_vehicle_contact_log_permissions AFTER INSERT ON public.vehicle_contact_log_pemissions FOR EACH ROW EXECUTE FUNCTION public.vehicle_contact_log_pemissions_update();



CREATE TRIGGER workshop_modified_notify AFTER INSERT OR DELETE OR UPDATE ON public.appointments FOR EACH ROW EXECUTE FUNCTION public.workshop_modified();



ALTER TABLE ONLY public.absence_calendar
    ADD CONSTRAINT absence_calendar_reason_fkey FOREIGN KEY (reason) REFERENCES public.absence_reasons(id) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.absence_calendar
    ADD CONSTRAINT absence_calendar_type_fkey FOREIGN KEY (type) REFERENCES public.absence_types(type) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_progress_status_fkey FOREIGN KEY (progress_status) REFERENCES public.wtp_progress_status(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_pseudo_vehicle_make_number_fkey FOREIGN KEY (pseudo_vehicle_make_number) REFERENCES public.makes(make_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_urgency_fkey FOREIGN KEY (urgency) REFERENCES public.wtp_urgency(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_vehicle_status_fkey FOREIGN KEY (vehicle_status) REFERENCES public.wtp_vehicle_status(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.charge_types
    ADD CONSTRAINT charge_types_type_fkey FOREIGN KEY (type) REFERENCES public.charge_type_descriptions(type) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.codes_customer_list
    ADD CONSTRAINT codes_customer_list_code_fkey FOREIGN KEY (code) REFERENCES public.codes_customer_def(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.codes_vehicle_date
    ADD CONSTRAINT codes_vehicle_date_code_fkey FOREIGN KEY (code) REFERENCES public.codes_vehicle_date_def(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.codes_vehicle_mileage
    ADD CONSTRAINT codes_vehicle_mileage_code_fkey FOREIGN KEY (code) REFERENCES public.codes_vehicle_mileage_def(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.customer_to_customercodes
    ADD CONSTRAINT customer_to_customercodes_customer_code_fkey FOREIGN KEY (customer_code) REFERENCES public.customer_codes(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.customer_to_professioncodes
    ADD CONSTRAINT customer_to_professioncodes_profession_code_fkey FOREIGN KEY (profession_code) REFERENCES public.customer_profession_codes(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_in_used_vehicle_buy_type_fkey FOREIGN KEY (in_used_vehicle_buy_type) REFERENCES public.vehicle_buy_types(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_out_make_number_fkey FOREIGN KEY (out_make_number) REFERENCES public.makes(make_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_out_sale_type_fkey FOREIGN KEY (out_sale_type) REFERENCES public.vehicle_sale_types(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_pre_owned_car_code_fkey FOREIGN KEY (pre_owned_car_code) REFERENCES public.vehicle_pre_owned_codes(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.employees_group_mapping
    ADD CONSTRAINT employees_group_mapping_employee_number_validity_date_fkey FOREIGN KEY (employee_number, validity_date) REFERENCES public.employees_history(employee_number, validity_date);



ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_credit_invoice_type_credit_invoice_number_fkey FOREIGN KEY (credit_invoice_type, credit_invoice_number) REFERENCES public.invoices(invoice_type, invoice_number);



ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_invoice_type_fkey FOREIGN KEY (invoice_type) REFERENCES public.invoice_types(type) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.journal_accountings
    ADD CONSTRAINT journal_accountings_customer_contra_account_fkey FOREIGN KEY (customer_contra_account) REFERENCES public.customers_suppliers(customer_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.journal_accountings
    ADD CONSTRAINT journal_accountings_customer_number_fkey FOREIGN KEY (customer_number) REFERENCES public.customers_suppliers(customer_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.journal_accountings
    ADD CONSTRAINT journal_accountings_document_type_fkey FOREIGN KEY (document_type) REFERENCES public.document_types(document_type_in_journal) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.journal_accountings
    ADD CONSTRAINT journal_accountings_subsidiary_to_company_ref_nominal_cont_fkey FOREIGN KEY (subsidiary_to_company_ref, nominal_contra_account) REFERENCES public.nominal_accounts(subsidiary_to_company_ref, nominal_account_number);



ALTER TABLE ONLY public.labours
    ADD CONSTRAINT labours_labour_type_fkey FOREIGN KEY (labour_type) REFERENCES public.labour_types(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.model_to_fuels
    ADD CONSTRAINT model_to_fuels_code_fkey FOREIGN KEY (code) REFERENCES public.fuels(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.model_to_fuels
    ADD CONSTRAINT model_to_fuels_make_number_model_code_fkey FOREIGN KEY (make_number, model_code) REFERENCES public.models(make_number, model_code);



ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_make_number_fkey FOREIGN KEY (make_number) REFERENCES public.makes(make_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_vehicle_body_fkey FOREIGN KEY (vehicle_body) REFERENCES public.vehicle_bodys(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_clearing_delay_type_fkey FOREIGN KEY (clearing_delay_type) REFERENCES public.clearing_delay_types(type) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_urgency_fkey FOREIGN KEY (urgency) REFERENCES public.wtp_urgency(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.parts_rebate_codes_buy
    ADD CONSTRAINT parts_rebate_codes_buy_rebate_group_code_fkey FOREIGN KEY (rebate_group_code) REFERENCES public.parts_rebate_groups_buy(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.parts_rebate_codes_sell
    ADD CONSTRAINT parts_rebate_codes_sell_rebate_group_code_fkey FOREIGN KEY (rebate_group_code) REFERENCES public.parts_rebate_groups_sell(code) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.privacy_details
    ADD CONSTRAINT privacy_details_channel_code_fkey FOREIGN KEY (channel_code) REFERENCES public.privacy_channels(channel_code);



ALTER TABLE ONLY public.privacy_details
    ADD CONSTRAINT privacy_details_scope_code_fkey FOREIGN KEY (scope_code) REFERENCES public.privacy_scopes(scope_code);



ALTER TABLE ONLY public.transit_vehicles
    ADD CONSTRAINT transit_vehicles_make_number_fkey FOREIGN KEY (make_number) REFERENCES public.makes(make_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.vehicles
    ADD CONSTRAINT vehicles_make_number_fkey FOREIGN KEY (make_number) REFERENCES public.makes(make_number) ON UPDATE CASCADE ON DELETE RESTRICT;



ALTER TABLE ONLY public.year_calendar
    ADD CONSTRAINT year_calendar_day_off_declaration_fkey FOREIGN KEY (day_off_declaration) REFERENCES public.year_calendar_day_off_codes(code) ON UPDATE CASCADE ON DELETE RESTRICT;



\unrestrict Opqeh4KMT09GRRlSPhlzEuEJ8bUGmh43oCOHnidZAECirOfoUS0s6twCjSnC1S1
