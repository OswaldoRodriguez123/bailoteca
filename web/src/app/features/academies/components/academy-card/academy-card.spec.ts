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
