import { Academy, AcademyLocation, AcademyStyle } from '../../core/models/academy.models';

const LINK_LABELS: Record<string, string> = {
  web: 'Sitio web',
  instagram: 'Instagram',
  facebook: 'Facebook',
  tiktok: 'TikTok',
  whatsapp: 'WhatsApp',
  phone: 'Teléfono',
  email: 'Email',
};

export function styleLabel(style: AcademyStyle): string {
  if (style.name) {
    return style.name;
  }

  const spaced = style.slug.replace(/-/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function linkLabel(kind: string): string {
  return LINK_LABELS[kind.toLowerCase()] ?? 'Enlace';
}

export function mapUrl(location: AcademyLocation): string | null {
  const base = 'https://www.google.com/maps/search/?api=1';

  if (location.lat !== null && location.lng !== null) {
    return `${base}&query=${location.lat},${location.lng}`;
  }

  const query = [location.address, location.comuna]
    .filter((value): value is string => Boolean(value))
    .join(', ');

  if (!query) {
    return null;
  }

  return `${base}&query=${encodeURIComponent(query).replace(/%20/g, '+')}`;
}

export function uniqueComunas(academy: Academy): string[] {
  const comunas = new Set<string>();

  for (const location of academy.locations) {
    if (location.comuna) {
      comunas.add(location.comuna);
    }
  }

  return [...comunas];
}

export function truncated(text: string | null, max = 140): string {
  if (!text) {
    return '';
  }

  if (text.length <= max) {
    return text;
  }

  return text.slice(0, max).trimEnd() + '…';
}
