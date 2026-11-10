import {
  Academy,
  AcademyLocation,
  AcademyPage,
  AcademyStyle,
  PAGE_SIZE,
} from '../models/academy.models';

export function makeStyle(overrides: Partial<AcademyStyle> = {}): AcademyStyle {
  return {
    slug: 'salsa',
    name: 'Salsa',
    confidence: 1,
    evidence: null,
    ...overrides,
  };
}

export function makeLocation(overrides: Partial<AcademyLocation> = {}): AcademyLocation {
  return {
    label: 'Sede Providencia',
    address: 'Av. Providencia 123',
    comuna: 'Providencia',
    lat: null,
    lng: null,
    source_url: null,
    ...overrides,
  };
}

export function makeAcademy(overrides: Partial<Academy> = {}): Academy {
  return {
    id: 'academy-1',
    slug: 'danson-academy',
    name: 'Dansón Academy',
    description: null,
    status: 'active',
    source_urls: [],
    created_at: null,
    updated_at: null,
    verified_at: null,
    locations: [],
    links: [],
    styles: [makeStyle()],
    google_place_id: null,
    google_name: null,
    google_address: null,
    google_rating: null,
    google_reviews: null,
    google_price: null,
    google_hours: null,
    google_open_state: null,
    google_maps_url: null,
    google_fetched_at: null,
    ...overrides,
  };
}

export function makePage(items: Academy[], overrides: Partial<AcademyPage> = {}): AcademyPage {
  return {
    items,
    page: 1,
    page_size: PAGE_SIZE,
    total: items.length,
    ...overrides,
  };
}
