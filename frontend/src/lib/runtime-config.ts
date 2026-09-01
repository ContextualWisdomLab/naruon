export interface RuntimeConfig {
  product_name: string;
  product_version: string;
  feature_flags: Record<string, boolean>;
}

interface RuntimeConfigWire {
  product_name: string;
  version: string;
  features: Record<string, boolean>;
}

let configCache: RuntimeConfig | null = null;
let fetchPromise: Promise<RuntimeConfig> | null = null;

function getRuntimeConfigErrorLogMetadata(error: unknown) {
  return {
    error_type: error instanceof Error ? error.name || 'Error' : typeof error,
  };
}

function translateRuntimeConfigWire(runtimeConfigWire: RuntimeConfigWire): RuntimeConfig {
  return {
    product_name: runtimeConfigWire.product_name,
    product_version: runtimeConfigWire.version,
    feature_flags: runtimeConfigWire.features,
  };
}

export async function fetchRuntimeConfig(baseUrl: string = ''): Promise<RuntimeConfig> {
  if (configCache) return configCache;
  if (fetchPromise) return fetchPromise;

  const configUrl = baseUrl ? `${baseUrl}/api/runtime-config` : '/api/runtime-config';

  fetchPromise = fetch(configUrl)
    .then((response) => {
      if (!response.ok) throw new Error('Failed to fetch runtime config');
      return response.json() as Promise<RuntimeConfigWire>;
    })
    .then((runtimeConfigWire) => {
      const runtimeConfig = translateRuntimeConfigWire(runtimeConfigWire);
      configCache = runtimeConfig;
      fetchPromise = null;
      return runtimeConfig;
    })
    .catch((fetchError) => {
      console.error(
        'Runtime config fetch failed, using fallback',
        getRuntimeConfigErrorLogMetadata(fetchError),
      );
      const fallbackConfig: RuntimeConfig = {
        product_name: 'Naruon',
        product_version: 'fallback',
        feature_flags: {},
      };
      configCache = fallbackConfig;
      fetchPromise = null;
      return fallbackConfig;
    });

  return fetchPromise;
}

export function getCachedConfig(): RuntimeConfig | null {
  return configCache;
}
