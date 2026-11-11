import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { makeAcademy, makeLocation, makeStyle } from '../../../../core/testing/academy.fixtures';
import { AcademyCard } from './academy-card';

describe('AcademyCard', () => {
  let fixture: ComponentFixture<AcademyCard>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AcademyCard],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(AcademyCard);
  });

  it('renderiza nombre, comunas, descripción y enlace con filtros', async () => {
    fixture.componentRef.setInput(
      'academy',
      makeAcademy({
        name: 'Dansón Academy',
        description: 'Clases de salsa y bachata en Providencia.',
        locations: [
          makeLocation({ comuna: 'Providencia' }),
          makeLocation({ comuna: 'Providencia' }),
          makeLocation({ comuna: 'Ñuñoa' }),
        ],
        styles: [makeStyle({ slug: 'salsa', name: 'Salsa' })],
      }),
    );
    fixture.componentRef.setInput('queryParams', { comuna: 'Providencia' });
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Dansón Academy');
    expect(element.textContent).toContain('Providencia');
    expect(element.textContent).toContain('Ñuñoa');
    expect(element.textContent).toContain('Clases de salsa y bachata en Providencia.');
    expect(element.textContent).toContain('Salsa');

    const link = element.querySelector('a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/academias/danson-academy?comuna=Providencia');
  });

  it('muestra el badge Cerrada sin crear otro enlace', async () => {
    fixture.componentRef.setInput('academy', makeAcademy({ status: 'closed' }));
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Cerrada');
    expect(element.querySelectorAll('a')).toHaveLength(1);
  });

  it('muestra la portada cuando la academia tiene cover_url', async () => {
    fixture.componentRef.setInput(
      'academy',
      makeAcademy({ cover_url: 'https://proj.supabase.co/storage/v1/object/public/academy-covers/danson-academy.jpg' }),
    );
    await fixture.whenStable();

    const img = fixture.nativeElement.querySelector('img') as HTMLImageElement | null;
    expect(img).not.toBeNull();
    expect(img!.getAttribute('src')).toBe(
      'https://proj.supabase.co/storage/v1/object/public/academy-covers/danson-academy.jpg',
    );
  });

  it('muestra las iniciales cuando la academia no tiene cover_url', async () => {
    fixture.componentRef.setInput('academy', makeAcademy({ cover_url: null }));
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('img')).toBeNull();
    expect(element.textContent).toContain('DA');
  });

  it('muestra las iniciales cuando la portada falla al cargar', async () => {
    fixture.componentRef.setInput(
      'academy',
      makeAcademy({ cover_url: 'https://img.example/roto.jpg' }),
    );
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    const img = element.querySelector('img');
    expect(img).not.toBeNull();

    img!.dispatchEvent(new Event('error'));
    await fixture.whenStable();

    expect(element.querySelector('img')).toBeNull();
    expect(element.textContent).toContain('DA');
  });

  it('tolera descripción, ubicaciones y estilos vacíos', async () => {
    fixture.componentRef.setInput(
      'academy',
      makeAcademy({ description: null, locations: [], styles: [] }),
    );

    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('p')).toBeNull();
    expect(element.textContent).not.toContain('undefined');
  });
});
