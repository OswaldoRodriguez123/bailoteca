import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { AcademyStyle } from '../../../../core/models/academy.models';
import { styleLabel } from '../../academy-display';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-style-badges',
  template: `
    @if (styles().length) {
      <ul class="flex flex-wrap gap-x-2 gap-y-1 text-sm text-muted" aria-label="Estilos">
        @for (style of styles(); track style.slug) {
          <li class="after:ml-2 after:content-['·'] last:after:content-none">
            <span>{{ label(style) }}</span>
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
