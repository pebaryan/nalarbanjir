import { TestBed } from '@angular/core/testing';
import { SimulationStore } from './simulation.store';

describe('SimulationStore', () => {
  let store: SimulationStore;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    store = TestBed.inject(SimulationStore);
  });

  it('should be created', () => {
    expect(store).toBeTruthy();
  });

  describe('initial state', () => {
    it('should default to 2d mode', () => {
      expect(store.mode()).toBe('2d');
    });

    it('should default to idle status', () => {
      expect(store.status()).toBe('idle');
    });

    it('should have zero time and steps', () => {
      expect(store.currentTime()).toBe(0);
      expect(store.stepCount()).toBe(0);
    });

    it('should not be ws connected by default', () => {
      expect(store.isWsConnected()).toBeFalse();
    });

    it('should have null stats by default', () => {
      expect(store.stats()).toBeNull();
    });

    it('should have null error message', () => {
      expect(store.errorMessage()).toBeNull();
    });

    it('should start with initCount 0', () => {
      expect(store.initCount()).toBe(0);
    });
  });

  describe('computed signals', () => {
    it('should format time with 1 decimal', () => {
      store.updateFromStep(10.123, 50, null);
      expect(store.formattedTime()).toBe('10.1 s');
    });

    it('should format step count', () => {
      store.updateFromStep(5, 42, null);
      expect(store.formattedStep()).toBe('Step 42');
    });

    it('should beRunning true when status is running', () => {
      store.setStatus('running');
      expect(store.isRunning()).toBeTrue();
    });

    it('should beRunning false when status is paused', () => {
      store.setStatus('paused');
      expect(store.isRunning()).toBeFalse();
    });

    it('should be hasError true when status is error', () => {
      store.setError('something failed');
      expect(store.hasError()).toBeTrue();
    });

    it('should show flooded area with 2 decimals', () => {
      store.updateFromStep(1, 1, {
        maxDepth: 2, meanDepth: 1, floodedCells: 100,
        floodedAreaKm2: 1.234, dominantRisk: 'moderate',
      });
      expect(store.floodedAreaStr()).toBe('1.23 km²');
    });

    it('should show max depth with 2 decimals', () => {
      store.updateFromStep(1, 1, {
        maxDepth: 3.456, meanDepth: 1, floodedCells: 100,
        floodedAreaKm2: 0, dominantRisk: 'none',
      });
      expect(store.maxDepthStr()).toBe('3.46 m');
    });

    it('should show dash when stats are null', () => {
      store.resetState();
      expect(store.floodedAreaStr()).toBe('—');
      expect(store.maxDepthStr()).toBe('—');
    });
  });

  describe('methods', () => {
    it('should set mode', () => {
      store.setMode('1d');
      expect(store.mode()).toBe('1d');

      store.setMode('1d2d');
      expect(store.mode()).toBe('1d2d');
    });

    it('should set status', () => {
      store.setStatus('running');
      expect(store.status()).toBe('running');
      expect(store.isRunning()).toBeTrue();

      store.setStatus('paused');
      expect(store.status()).toBe('paused');
      expect(store.isRunning()).toBeFalse();
    });

    it('should update time, step, and stats', () => {
      store.updateFromStep(10.5, 100, {
        maxDepth: 5, meanDepth: 2, floodedCells: 500,
        floodedAreaKm2: 2.5, dominantRisk: 'major',
      });
      expect(store.currentTime()).toBe(10.5);
      expect(store.stepCount()).toBe(100);
      expect(store.stats()?.maxDepth).toBe(5);
      expect(store.stats()?.dominantRisk).toBe('major');
    });

    it('should set ws connected', () => {
      store.setWsConnected(true);
      expect(store.isWsConnected()).toBeTrue();

      store.setWsConnected(false);
      expect(store.isWsConnected()).toBeFalse();
    });

    it('should set error status and message', () => {
      store.setError('connection lost');
      expect(store.status()).toBe('error');
      expect(store.errorMessage()).toBe('connection lost');
      expect(store.hasError()).toBeTrue();
    });

    it('should reset to initial state', () => {
      store.setStatus('running');
      store.updateFromStep(100, 500, {
        maxDepth: 10, meanDepth: 5, floodedCells: 1000,
        floodedAreaKm2: 50, dominantRisk: 'severe',
      });
      store.setError('test error');

      store.resetState();

      expect(store.status()).toBe('idle');
      expect(store.currentTime()).toBe(0);
      expect(store.stepCount()).toBe(0);
      expect(store.stats()).toBeNull();
      expect(store.errorMessage()).toBeNull();
      expect(store.mode()).toBe('2d');
    });

    it('should increment initCount on markInitialized', () => {
      expect(store.initCount()).toBe(0);
      store.markInitialized();
      expect(store.initCount()).toBe(1);
      store.markInitialized();
      expect(store.initCount()).toBe(2);
    });
  });
});
