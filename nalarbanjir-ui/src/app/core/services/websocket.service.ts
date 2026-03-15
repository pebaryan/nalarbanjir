import { Injectable, OnDestroy } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Observable, EMPTY, Subject } from 'rxjs';
import { catchError, switchAll, tap } from 'rxjs/operators';

export interface WsMessage {
  type: string;
  [key: string]: unknown;
}

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private ws$: WebSocketSubject<WsMessage> | null = null;
  private readonly _message$ = new Subject<WsMessage>();

  /** Observable stream of all incoming WebSocket messages. */
  readonly messages$: Observable<WsMessage> = this._message$.asObservable();

  connect(url: string): void {
    if (this.ws$) {
      return; // already connected
    }
    this.ws$ = webSocket<WsMessage>(url);
    this.ws$.pipe(
      catchError(() => EMPTY),
    ).subscribe({
      next: msg => this._message$.next(msg),
      complete: () => this.ws$ = null,
    });
  }

  send(message: WsMessage): void {
    this.ws$?.next(message);
  }

  ping(): void {
    this.send({ type: 'ping' });
  }

  disconnect(): void {
    this.ws$?.complete();
    this.ws$ = null;
  }

  get connected(): boolean {
    return this.ws$ !== null;
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
