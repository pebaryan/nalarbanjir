import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withFetch } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiService, SimulationMode, TerrainInfo } from './api.service';

describe('ApiService', () => {
  let service: ApiService;
  let http: HttpClient;
  let httpMock: HttpTestingController;
  const baseUrl = '/api';

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withFetch()),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(ApiService);
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('simulation endpoints', () => {
    it('should start a simulation via POST /simulation/start', () => {
      const req = { mode: '2d' as SimulationMode, steps: 100 };
      const resp = { ok: true, mode: '2d', message: 'started' };

      service.startSimulation(req).subscribe(result => {
        expect(result).toEqual(resp);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/start`);
      expect(reqObj.request.method).toBe('POST');
      expect(reqObj.request.body).toEqual(req);
      reqObj.flush(resp);
    });

    it('should get simulation status via GET /simulation/status', () => {
      const status = { status: 'running', current_step: 50, total_steps: 100, elapsed_time: 10 };

      service.getStatus().subscribe(result => {
        expect(result).toEqual(status);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/status`);
      expect(reqObj.request.method).toBe('GET');
      reqObj.flush(status);
    });

    it('should step the simulation with default n=1', () => {
      const state = { mode: '2d' as SimulationMode, status: 'running', current_step: 1, elapsed_time: 0.1 };

      service.step().subscribe(result => {
        expect(result).toEqual(state);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/step?n=1`);
      expect(reqObj.request.method).toBe('POST');
      reqObj.flush(state);
    });

    it('should step the simulation with custom n', () => {
      const state = { mode: '2d' as SimulationMode, status: 'running', current_step: 10, elapsed_time: 1 };

      service.step(10).subscribe(result => {
        expect(result).toEqual(state);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/step?n=10`);
      expect(reqObj.request.method).toBe('POST');
      reqObj.flush(state);
    });

    it('should get simulation state via GET /simulation/state', () => {
      const state = { mode: '2d' as SimulationMode, status: 'running', current_step: 10, elapsed_time: 1 };

      service.getState().subscribe(result => {
        expect(result).toEqual(state);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/state`);
      expect(reqObj.request.method).toBe('GET');
      reqObj.flush(state);
    });

    it('should reset simulation via POST /simulation/reset', () => {
      const resp = { ok: true, message: 'reset' };

      service.reset().subscribe(result => {
        expect(result).toEqual(resp);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/reset`);
      expect(reqObj.request.method).toBe('POST');
      reqObj.flush(resp);
    });
  });

  describe('terrain endpoints', () => {
    it('should get terrain info', () => {
      const info: TerrainInfo = {
        nx: 100, ny: 100, dx: 10, dy: 10,
        min_elevation: 0, max_elevation: 50, source: 'synthetic',
      };

      service.getTerrainInfo().subscribe(result => {
        expect(result).toEqual(info);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/terrain/info`);
      expect(reqObj.request.method).toBe('GET');
      reqObj.flush(info);
    });

    it('should get terrain mesh', () => {
      const mesh = { nx: 10, ny: 10, dx: 10, dy: 10, elevation: Array(10).fill(Array(10).fill(0)) };

      service.getTerrainMesh().subscribe(result => {
        expect(result.nx).toBe(10);
        expect(result.ny).toBe(10);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/terrain/mesh`);
      reqObj.flush(mesh);
    });
  });

  describe('prediction endpoints', () => {
    it('should get risk grid', () => {
      const risk = { nx: 10, ny: 10, risk_grid: Array(10).fill(Array(10).fill(0)), summary: {} };

      service.getRiskGrid().subscribe(result => {
        expect(result.nx).toBe(10);
        expect(result.ny).toBe(10);
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/prediction/risk`);
      reqObj.flush(risk);
    });
  });

  describe('error handling', () => {
    it('should emit error on HTTP failure', () => {
      let errorCalled = false;

      service.getStatus().subscribe({
        error: () => { errorCalled = true; },
      });

      const reqObj = httpMock.expectOne(`${baseUrl}/simulation/status`);
      reqObj.error(new ProgressEvent('error'));

      expect(errorCalled).toBeTrue();
    });
  });
});
