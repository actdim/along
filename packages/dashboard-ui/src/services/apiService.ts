import {
  registerAdapters,
  getMsgChannelSelector,
  type MsgProviderAdapter,
} from '@actdim/msgmesh/adapters';
import { DashboardApiClient } from '../api/client';
import { dashboardBus, type DashboardChannelPrefix } from '../bus';
import { FullDashboardData } from '../types';

/**
 * Service Provider wrapping NSwag DashboardApiClient via standard MsgMesh dynamic adapters.
 */
export class DashboardApiService {
  private static instance: DashboardApiService | null = null;
  private sseSource: EventSource | null = null;
  private client: DashboardApiClient;

  constructor() {
    this.client = new DashboardApiClient();
  }

  static start(): DashboardApiService {
    if (!this.instance) {
      this.instance = new DashboardApiService();
      this.instance.registerAdapter();
      this.instance.connectSSE();
    }
    return this.instance;
  }

  static stop(): void {
    if (this.instance) {
      if (this.instance.sseSource) {
        this.instance.sseSource.close();
        this.instance.sseSource = null;
      }
      this.instance = null;
    }
  }

  private registerAdapter() {
    const services: Record<DashboardChannelPrefix, any> = {
      'API.DASHBOARD.': this.client,
    };

    const adapters = Object.entries(services).map(
      ([_, service]) =>
        ({
          service,
          channelSelector: getMsgChannelSelector(services),
        }) as MsgProviderAdapter,
    );

    registerAdapters(dashboardBus, adapters);
  }

  private connectSSE() {
    try {
      this.sseSource = new EventSource('/api/events');

      this.sseSource.onopen = () => {
        dashboardBus.send({
          channel: 'APP.SSE.STATUS',
          payload: { connected: true },
        });
      };

      this.sseSource.addEventListener('reload', async () => {
        console.log('[SSE] File change detected -> reloading dashboard data via client...');
        try {
          const data: FullDashboardData = await this.client.getFullData();
          dashboardBus.send({
            channel: 'APP.DATA.UPDATED',
            payload: data,
          });
        } catch (err) {
          console.error('[SSE] Failed refreshing data:', err);
        }
      });

      this.sseSource.onerror = () => {
        dashboardBus.send({
          channel: 'APP.SSE.STATUS',
          payload: { connected: false },
        });
      };
    } catch {
      dashboardBus.send({
        channel: 'APP.SSE.STATUS',
        payload: { connected: false },
      });
    }
  }
}
