import {
  Academy,
  AcademyLocation,
  AcademyPage,
  AcademyStyle,
  GooglePlace,
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
    google: null,
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

export function makeGoogle(overrides: Partial<GooglePlace> = {}): GooglePlace {
  return {
    place_id: 'place-1',
    name: 'Dansón Academy',
    address: 'Av. Providencia 123',
    rating: null,
    reviews: null,
    price: null,
    hours: null,
    open_state: null,
    maps_url: null,
    thumbnail: null,
    phone: null,
    website: null,
    type: null,
    gps_coordinates: null,
    raw: null,
    fetched_at: null,
    ...overrides,
  };
}
