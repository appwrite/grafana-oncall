import '@grafana/data';

declare module '@grafana/data' {
  interface FeatureToggles {
    accessControlOnCall?: boolean;
  }
}
