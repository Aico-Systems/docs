#!/usr/bin/env bun
import postgres from "postgres";
import { parseArgs } from "util";

// Allowed search types for the CLI
type SearchType = "phone" | "name" | "plate";

const args = parseArgs({
	options: {
		phone: { type: "string" },
		name: { type: "string" },
		plate: { type: "string" },
		limit: { type: "string" },
	},
	allowPositionals: true,
});

const limit = Number.parseInt(args.values.limit ?? "15", 10) || 15;
const dbUrl = process.env.DATABASE_URL ?? buildDbUrlFromParts();
if (!dbUrl) {
	console.error(
		"DATABASE_URL env var is required. Could not build from .env (BENUTZER/PASSWORT/IP_ADRESSE_STANDORT_ZEVEN/POSTGRESQL_DATENBANK).",
	);
	process.exit(1);
}

function buildDbUrlFromParts(): string | null {
	const host = process.env.IP_ADRESSE_STANDORT_ZEVEN;
	const port = process.env.POSTGRESQL_PORT ?? "5432";
	const db = process.env.POSTGRESQL_DATENBANK;
	const user = process.env.BENUTZER;
	const pass = process.env.PASSWORT;

	if (!host || !db || !user || !pass) return null;
	return `postgres://${encodeURIComponent(user)}:${encodeURIComponent(pass)}@${host}:${port}/${db}`;
}

const sql = postgres(dbUrl, { prepare: true });

function normalizePhone(input: string): string {
	return input.replace(/[^\d+]/g, "");
}

function normalizePlate(input: string): string {
	return input.toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function normalizeName(input: string): string {
	return input.trim().toLowerCase().replace(/\s+/g, " ");
}

function resolveSearch(): { type: SearchType; term: string } {
	if (args.values.phone) return { type: "phone", term: args.values.phone };
	if (args.values.name) return { type: "name", term: args.values.name };
	if (args.values.plate) return { type: "plate", term: args.values.plate };

	const positional = args.positionals[0];
	if (!positional) {
		console.error(
			"Usage: bun user_lookup.ts --phone <digits> | --name <name> | --plate <license> [--limit N]",
		);
		process.exit(1);
	}

	if (/^[+0-9()\s.-]{6,}$/.test(positional))
		return { type: "phone", term: positional };
	if (/^[A-Za-zÄÖÜäöü0-9\s-]{4,}$/.test(positional)) {
		// Heuristic: if it contains digits and letters it is likely a plate
		const hasLetters = /[A-Za-zÄÖÜäöü]/.test(positional);
		const hasDigits = /\d/.test(positional);
		if (hasLetters && hasDigits) return { type: "plate", term: positional };
	}
	return { type: "name", term: positional };
}

async function fetchCustomers(matchesQuery: any) {
	return sql`
    WITH matches AS (
      ${matchesQuery}
    )
    SELECT
      c.customer_number,
      c.is_natural_person,
      c.is_dummy_customer,
      c.is_supplier,
      c.salutation_code,
      c.name_prefix,
      c.first_name,
      c.family_name,
      c.name_postfix,
      c.country_code,
      c.zip_code,
      c.home_city,
      c.home_street,
      c.birthday,
      c.last_contact,
      c.preferred_com_number_type,
      c.contact_salutation_code,
      c.contact_first_name,
      c.contact_family_name,
      contacts.contacts,
      vehicles.vehicles,
      notes.text AS top_note
    FROM matches m
    JOIN public.customers_suppliers c ON c.customer_number = m.customer_number
    LEFT JOIN LATERAL (
      SELECT json_agg(
        jsonb_strip_nulls(
          jsonb_build_object(
            'com_type', cn.com_type,
            'is_reference', cn.is_reference,
            'address', cn.address,
            'search_address', cn.search_address,
            'phone_number', cn.phone_number,
            'contact_firstname', cn.contact_firstname,
            'contact_lastname', cn.contact_lastname,
            'note', cn.note
          )
        )
        ORDER BY cn.is_reference DESC, cn.com_type, cn.counter
      ) AS contacts
      FROM public.customer_com_numbers cn
      WHERE cn.customer_number = c.customer_number
    ) contacts ON true
    LEFT JOIN LATERAL (
      SELECT json_agg(
        jsonb_strip_nulls(
          jsonb_build_object(
            'internal_number', v.internal_number,
            'license_plate', v.license_plate,
            'license_plate_country', v.license_plate_country,
            'license_plate_season', v.license_plate_season,
            'vin', v.vin,
            'make_number', v.make_number,
            'make_description', mk.description,
            'model_code', v.model_code,
            'model_description', md.description,
            'model_body', md.vehicle_body,
            'is_roadworthy', v.is_roadworthy,
            'is_customer_vehicle', v.is_customer_vehicle,
            'production_year', v.production_year,
            'first_registration_date', v.first_registration_date,
            'readmission_date', v.readmission_date,
            'next_service_date', v.next_service_date,
            'next_service_km', v.next_service_km,
            'next_emission_test_date', v.next_emission_test_date,
            'next_general_inspection_date', v.next_general_inspection_date,
            'mileage_km', v.mileage_km,
            'mileage_miles', v.mileage_miles,
            'power_kw', v.power_kw,
            'cubic_capacity', v.cubic_capacity,
            'owner_number', v.owner_number,
            'holder_number', v.holder_number,
            'previous_owner_number', v.previous_owner_number,
            'last_change_date', v.last_change_date
          )
        )
        ORDER BY v.last_change_date DESC NULLS LAST, v.internal_number
      ) AS vehicles
      FROM public.vehicles v
      LEFT JOIN public.makes mk ON mk.make_number = v.make_number
      LEFT JOIN public.models md ON md.make_number = v.make_number AND md.model_code = v.model_code
      WHERE v.owner_number = c.customer_number
         OR v.holder_number = c.customer_number
         OR v.previous_owner_number = c.customer_number
    ) vehicles ON true
    LEFT JOIN public.customer_top_note notes ON notes.customer_number = c.customer_number
    ORDER BY c.customer_number
    LIMIT ${limit};
  `;
}

async function lookupByPhone(term: string) {
	const normalized = normalizePhone(term);
	const matches = sql`
    SELECT DISTINCT cn.customer_number
    FROM public.customer_com_numbers cn
    WHERE regexp_replace(coalesce(cn.phone_number, ''), '[^0-9+]', '', 'g') ILIKE '%' || ${normalized} || '%'
       OR regexp_replace(coalesce(cn.search_address, ''), '[^0-9+]', '', 'g') ILIKE '%' || ${normalized} || '%'
    LIMIT ${limit * 5}
  `;
	return fetchCustomers(matches);
}

async function lookupByName(term: string) {
	const normalized = normalizeName(term);
	const matches = sql`
    SELECT DISTINCT c.customer_number
    FROM public.customers_suppliers c
    WHERE lower(concat_ws(' ', c.name_prefix, c.first_name, c.family_name, c.name_postfix)) LIKE '%' || ${normalized} || '%'
       OR lower(concat_ws(' ', c.contact_first_name, c.contact_family_name)) LIKE '%' || ${normalized} || '%'
    ORDER BY c.customer_number
    LIMIT ${limit * 5}
  `;
	return fetchCustomers(matches);
}

async function lookupByPlate(term: string) {
	const normalized = normalizePlate(term);
	const matches = sql`
    SELECT DISTINCT num AS customer_number
    FROM public.vehicles v
    CROSS JOIN LATERAL unnest(ARRAY[v.owner_number, v.holder_number, v.previous_owner_number]) AS num
    WHERE num IS NOT NULL AND num > 0
      AND regexp_replace(coalesce(v.license_plate, ''), '[^A-Za-z0-9]', '', 'g') ILIKE '%' || ${normalized} || '%'
    LIMIT ${limit * 5}
  `;

	const customers = await fetchCustomers(matches);
	const vehicles = await sql`
    SELECT v.internal_number, v.license_plate, v.license_plate_country, v.license_plate_season, v.vin,
           v.make_number, mk.description AS make_description,
           v.model_code, md.description AS model_description, md.vehicle_body,
           v.is_roadworthy, v.is_customer_vehicle, v.production_year,
           v.first_registration_date, v.readmission_date,
           v.next_service_date, v.next_service_km,
           v.next_emission_test_date, v.next_general_inspection_date,
           v.mileage_km, v.mileage_miles, v.power_kw, v.cubic_capacity,
           v.owner_number, v.holder_number, v.previous_owner_number,
           v.last_change_date
    FROM public.vehicles v
    LEFT JOIN public.makes mk ON mk.make_number = v.make_number
    LEFT JOIN public.models md ON md.make_number = v.make_number AND md.model_code = v.model_code
    WHERE regexp_replace(coalesce(license_plate, ''), '[^A-Za-z0-9]', '', 'g') ILIKE '%' || ${normalized} || '%'
    ORDER BY last_change_date DESC NULLS LAST, internal_number
    LIMIT ${limit * 3}
  `;

	return { customers, vehicles };
}

async function main() {
	const { type, term } = resolveSearch();
	let result: unknown;

	if (type === "phone") result = await lookupByPhone(term);
	else if (type === "name") result = await lookupByName(term);
	else result = await lookupByPlate(term);

	console.log(
		JSON.stringify(
			{
				search: { type, term, limit },
				...(type === "plate" && (result as any).vehicles
					? {
							customers: (result as any).customers,
							vehicles: (result as any).vehicles,
						}
					: { customers: result }),
			},
			null,
			2,
		),
	);
}

main()
	.catch((err) => {
		console.error("Lookup failed", err);
		process.exit(1);
	})
	.finally(() => sql.end({ timeout: 1 }));
