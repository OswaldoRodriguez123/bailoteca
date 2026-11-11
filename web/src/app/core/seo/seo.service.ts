import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

import { SITE_URL } from './site-url';

export type SeoJsonLd = Record<string, unknown>;

export interface SeoMetadata {
  title: string;
  description: string;
  path: string;
  image?: string;
  imageAlt?: string;
  imageWidth?: number;
  imageHeight?: number;
  type?: string;
  noindex?: boolean;
  jsonLd?: SeoJsonLd | SeoJsonLd[];
}

const SITE_NAME = 'Bailoteca';
const DEFAULT_TITLE = 'Bailoteca — Academias de baile en Santiago';
const MANAGED_ATTRIBUTE = 'data-seo';
const MANAGED_SELECTOR = `[${MANAGED_ATTRIBUTE}]`;

@Injectable({ providedIn: 'root' })
export class SeoService {
  private readonly title = inject(Title);
  private readonly meta = inject(Meta);
  private readonly doc = inject(DOCUMENT);
  private readonly siteUrl = inject(SITE_URL);

  set(meta: SeoMetadata): void {
    this.clear();

    const title = `${meta.title} · ${SITE_NAME}`;
    const url = this.absolute(meta.path);

    this.title.setTitle(title);
    this.addMeta('name', 'description', meta.description);
    this.addMeta('name', 'robots', meta.noindex ? 'noindex, follow' : 'index, follow');
    this.addMeta('property', 'og:title', title);
    this.addMeta('property', 'og:description', meta.description);
    this.addMeta('property', 'og:url', url);
    this.addMeta('property', 'og:type', meta.type ?? 'website');
    this.addMeta('property', 'og:site_name', SITE_NAME);
    this.addMeta('property', 'og:locale', 'es_CL');
    this.addMeta('name', 'twitter:card', 'summary_large_image');
    this.addMeta('name', 'twitter:title', title);
    this.addMeta('name', 'twitter:description', meta.description);

    if (meta.image) {
      const image = this.absolute(meta.image);
      this.addMeta('property', 'og:image', image);
      this.addMeta('name', 'twitter:image', image);

      if (meta.imageAlt) {
        this.addMeta('property', 'og:image:alt', meta.imageAlt);
        this.addMeta('name', 'twitter:image:alt', meta.imageAlt);
      }
      if (meta.imageWidth) {
        this.addMeta('property', 'og:image:width', String(meta.imageWidth));
      }
      if (meta.imageHeight) {
        this.addMeta('property', 'og:image:height', String(meta.imageHeight));
      }
    }

    if (meta.jsonLd) {
      this.addJsonLd(meta.jsonLd);
    }

    this.addCanonical(url);
  }

  clear(): void {
    this.doc.head
      .querySelectorAll(
        `meta${MANAGED_SELECTOR}, link${MANAGED_SELECTOR}, script${MANAGED_SELECTOR}`,
      )
      .forEach(element => element.remove());
    this.title.setTitle(DEFAULT_TITLE);
  }

  private addMeta(attribute: 'name' | 'property', key: string, content: string): void {
    this.meta.addTag({ [attribute]: key, content, 'data-seo': '' });
  }

  private addJsonLd(value: SeoJsonLd | SeoJsonLd[]): void {
    const script = this.doc.createElement('script');
    script.setAttribute('type', 'application/ld+json');
    script.setAttribute('data-seo', '');
    script.textContent = JSON.stringify(value);
    this.doc.head.appendChild(script);
  }

  private addCanonical(url: string): void {
    const link = this.doc.createElement('link');
    link.setAttribute('rel', 'canonical');
    link.setAttribute('href', url);
    link.setAttribute('data-seo', '');
    this.doc.head.appendChild(link);
  }

  private absolute(path: string): string {
    return new URL(path, this.siteUrl).toString();
  }
}
