import { PAGE_SIZE } from '../../core/models/academy.models';

export function lastPage(total: number, pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
