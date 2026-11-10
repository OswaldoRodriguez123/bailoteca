import { ComponentFixture, TestBed } from '@angular/core/testing';

import { makeStyle } from '../../../../core/testing/academy.fixtures';
import { StyleBadges } from './style-badges';

describe('StyleBadges', () => {
  let fixture: ComponentFixture<StyleBadges>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [StyleBadges] }).compileComponents();
    fixture = TestBed.createComponent(StyleBadges);
  });

  it('renderiza un badge por estilo y capitaliza el slug cuando falta el nombre', async () => {
    fixture.componentRef.setInput('styles', [
      makeStyle({ slug: 'salsa', name: null }),
      makeStyle({ slug: 'bachata', name: 'Bachata' }),
    ]);
    await fixture.whenStable();

    const badges = fixture.nativeElement.querySelectorAll('span');
    expect(badges).toHaveLength(2);
    expect(badges[0].textContent).toContain('Salsa');
    expect(badges[1].textContent).toContain('Bachata');
  });
});
