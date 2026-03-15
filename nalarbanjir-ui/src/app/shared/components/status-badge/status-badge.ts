import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="badge" [class]="'badge--' + status()">
      {{ statusLabel() }}
    </span>
  `,
  styles: [`
    .badge {
      display: inline-block;
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .badge--idle      { background: #374151; color: #9ca3af; }
    .badge--running   { background: #065f46; color: #6ee7b7; }
    .badge--paused    { background: #78350f; color: #fcd34d; }
    .badge--error     { background: #7f1d1d; color: #fca5a5; }
    .badge--connected { background: #1e3a5f; color: #93c5fd; }
  `],
})
export class StatusBadge {
  readonly status = input<string>('idle');

  statusLabel(): string {
    return this.status();
  }
}
