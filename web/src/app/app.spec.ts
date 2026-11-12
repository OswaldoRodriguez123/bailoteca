import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('renders the brand and the router outlet', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;

    expect(compiled.querySelector('header')?.textContent).toContain('Bailoteca');
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('atribuye la geocodificación a OpenStreetMap', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('footer')?.textContent)
      .toContain('OpenStreetMap contributors');
  });

  it('enlaza la página Acerca de desde el pie', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;

    expect(compiled.querySelector('footer a[href="/acerca"]')?.textContent).toContain(
      'Acerca de',
    );
  });
});
