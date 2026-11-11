import {
  Academy,
  AcademyLink,
  AcademyLocation,
  AcademyStyle,
} from '../../core/models/academy.models';

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

export function linkHref(link: AcademyLink): string {
  const kind = link.kind.toLowerCase();

  if (kind === 'phone' && !/^tel:/i.test(link.url)) {
    return `tel:${link.url.replace(/[^\d+]/g, '')}`;
  }

  if (kind === 'email' && !/^mailto:/i.test(link.url)) {
    return `mailto:${link.url}`;
  }

  return link.url;
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

const SHARE_PATTERNS = [/share\.php/i, /\/sharer/i, /intent\/tweet/i, /\/share\?/i];

export function socialProfiles(links: AcademyLink[]): string[] {
  const seen = new Set<string>();

  for (const link of links) {
    const url = link.url.trim();
    if (!/^https?:\/\//i.test(url)) {
      continue;
    }
    if (SHARE_PATTERNS.some(pattern => pattern.test(url))) {
      continue;
    }
    seen.add(url);
  }

  return [...seen];
}

const DAYS: Record<string, string> = {
  lunes: 'Monday',
  martes: 'Tuesday',
  miércoles: 'Wednesday',
  jueves: 'Thursday',
  viernes: 'Friday',
  sábado: 'Saturday',
  domingo: 'Sunday',
  monday: 'Monday',
  tuesday: 'Tuesday',
  wednesday: 'Wednesday',
  thursday: 'Thursday',
  friday: 'Friday',
  saturday: 'Saturday',
  sunday: 'Sunday',
};

interface OpeningHoursSpec {
  '@type': 'OpeningHoursSpecification';
  dayOfWeek: string;
  opens: string;
  closes: string;
}

export function openingHoursSpecification(
  hours: Record<string, string> | null,
): OpeningHoursSpec[] {
  if (!hours) {
    return [];
  }

  const specs: OpeningHoursSpec[] = [];

  for (const [day, value] of Object.entries(hours)) {
    const dayOfWeek = DAYS[day.trim().toLowerCase()];
    const range = parseHours(value);
    if (!dayOfWeek || !range) {
      continue;
    }
    specs.push({
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: `https://schema.org/${dayOfWeek}`,
      opens: range.opens,
      closes: range.closes,
    });
  }

  return specs;
}

function parseHours(value: string): { opens: string; closes: string } | null {
  const text = value.trim().toLowerCase();
  if (!text || text.includes('cerrado')) {
    return null;
  }

  const match = text.match(
    /(\d{1,2})(?::(\d{2}))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)?\s*[–\-—]\s*(\d{1,2})(?::(\d{2}))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)?/,
  );
  if (!match) {
    return null;
  }

  const [, startHour, startMinute, startMeridiem, endHour, endMinute, endMeridiem] = match;
  const meridiem = endMeridiem ?? startMeridiem;

  const opens = to24(startHour, startMinute, startMeridiem ?? meridiem);
  const closes = to24(endHour, endMinute, meridiem);

  if (!opens || !closes) {
    return null;
  }

  return { opens, closes };
}

function to24(hour: string, minute: string | undefined, meridiem: string | undefined): string | null {
  let value = Number(hour);
  if (Number.isNaN(value) || value > 23) {
    return null;
  }

  const isPm = Boolean(meridiem && meridiem.startsWith('p'));
  const isAm = Boolean(meridiem && meridiem.startsWith('a'));

  if (isPm && value < 12) {
    value += 12;
  }
  if (isAm && value === 12) {
    value = 0;
  }

  return `${String(value).padStart(2, '0')}:${minute ?? '00'}`;
}

export function normalizePhone(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const digits = value.replace(/\D/g, '');
  if (!digits) {
    return null;
  }

  if (digits.startsWith('56')) {
    return `+${digits}`;
  }

  return `+56${digits}`;
}

export function breadcrumbList(name: string, path: string, siteUrl: string): Record<string, unknown> {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      {
        '@type': 'ListItem',
        position: 1,
        name: 'Inicio',
        item: new URL('/', siteUrl).toString(),
      },
      {
        '@type': 'ListItem',
        position: 2,
        name,
        item: new URL(path, siteUrl).toString(),
      },
    ],
  };
}
