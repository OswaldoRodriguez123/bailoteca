import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LoadingGrid } from './loading-grid';

describe('LoadingGrid', () => {
  let fixture: ComponentFixture<LoadingGrid>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [LoadingGrid] }).compileComponents();
    fixture = TestBed.createComponent(LoadingGrid);
  });

  it('renderiza la cantidad de skeletons pedida', async () => {
    fixture.componentRef.setInput('count', 3);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(element.querySelectorAll('[aria-hidden="true"]')).toHaveLength(3);
  });
});
