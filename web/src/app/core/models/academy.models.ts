export const PAGE_SIZE = 20;

export interface AcademyLocation {
  label: string | null;
  address: string | null;
  comuna: string | null;
  lat: number | null;
  lng: number | null;
  source_url: string | null;
}

export interface AcademyLink {
  kind: string;
  url: string;
}

export interface AcademyStyle {
  slug: string;
  name: string | null;
  confidence: number | null;
  evidence: string | null;
}

export interface Academy {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  status: string;
  source_urls: string[];
  created_at: string | null;
  updated_at: string | null;
  verified_at: string | null;
  locations: AcademyLocation[];
  links: AcademyLink[];
  styles: AcademyStyle[];
  google_place_id: string | null;
  google_name: string | null;
  google_address: string | null;
  google_rating: number | null;
  google_reviews: number | null;
  google_price: string | null;
  google_hours: Record<string, string> | null;
  google_open_state: string | null;
  google_maps_url: string | null;
  google_fetched_at: string | null;
}

export interface AcademyPage {
  items: Academy[];
  page: number;
  page_size: number;
  total: number;
}

export interface StyleOption {
  slug: string;
  name: string;
  sort: number;
}

export interface AcademyQuery {
  comuna?: string | null;
  style?: string | null;
  q?: string | null;
  page?: number | null;
  pageSize?: number | null;
}
