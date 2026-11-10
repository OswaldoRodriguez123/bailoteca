import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { AcademyStyle } from '../../../../core/models/academy.models';
import { styleLabel } from '../../academy-display';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-style-badges',
  template: `
    @if (styles().length) {
      <ul class="flex flex-wrap gap-2" aria-label="Estilos">
        @for (style of styles(); track style.slug) {
          <li>
            <span class="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700">
              {{ label(style) }}
            </span>
          </li>
        }
      </ul>
    }
  `,
})
export class StyleBadges {
  readonly styles = input.required<AcademyStyle[]>();

  protected label(style: AcademyStyle): string {
    return styleLabel(style);
  }
}
