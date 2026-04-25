import api from './client'

export interface Region {
  id: number
  code: string
  name: string
  federal_district: string | null
}

export interface Municipality {
  id: number
  oktmo_code: string | null
  name: string
  municipality_type: string
  region_id: number
  region_name: string | null
  latitude: number | null
  longitude: number | null
  area_sq_km?: number | null
  population?: number | null
}

export interface PopulationTimeseriesPoint {
  year: number
  population: number | null
}

export interface PopulationTimeseries {
  municipality_id: number
  municipality_name: string
  data: PopulationTimeseriesPoint[]
}

export interface PopulationRankingItem {
  municipality_id: number
  municipality_name: string
  region_id: number
  region_name: string
  population_start: number | null
  population_end: number | null
  change_absolute: number | null
  change_percent: number | null
}

export interface PopulationSummary {
  total_population: number
  total_municipalities: number
  avg_growth_percent: number | null
  max_growth_municipality: string | null
  max_decline_municipality: string | null
}

export interface DemographicsTimeseriesPoint {
  year: number
  births: number | null
  deaths: number | null
  natural_growth: number | null
  net_migration: number | null
  birth_rate: number | null
  death_rate: number | null
  natural_growth_rate: number | null
  net_migration_rate: number | null
}

export interface DemographicsTimeseries {
  municipality_id: number
  municipality_name: string
  data: DemographicsTimeseriesPoint[]
}

export interface DemographicsSummary {
  total_births: number | null
  total_deaths: number | null
  total_natural_growth: number | null
  total_net_migration: number | null
  avg_birth_rate: number | null
  avg_death_rate: number | null
  avg_natural_growth_rate: number | null
  avg_net_migration_rate: number | null
}

export const fetchRegions = () =>
  api.get<Region[]>('/regions').then(r => r.data)

export const fetchMunicipalities = (params: {
  search?: string
  type?: string
  region_id?: number
  limit?: number
}) => api.get<Municipality[]>('/municipalities', { params }).then(r => r.data)

export const fetchMunicipalitiesByRegion = (regionId: number, params?: { year?: number }) =>
  api.get<Municipality[]>(`/regions/${regionId}/municipalities`, { params }).then(r => r.data)

export const fetchPopulationTimeseries = (params: {
  municipality_id: number[]
  region_id?: number
  year_from?: number
  year_to?: number
}) => api.get<PopulationTimeseries[]>('/population/timeseries', { params, paramsSerializer: { indexes: null } }).then(r => r.data)

export const fetchPopulationRankings = (params: {
  year_from?: number
  year_to?: number
  order?: 'asc' | 'desc'
  limit?: number
  region_id?: number
}) => api.get<PopulationRankingItem[]>('/population/rankings', { params }).then(r => r.data)

export const fetchPopulationSummary = (params: {
  year?: number
  region_id?: number
}) => api.get<PopulationSummary>('/population/summary', { params }).then(r => r.data)

export const fetchDemographicsTimeseries = (params: {
  municipality_id: number[]
  region_id?: number
  year_from?: number
  year_to?: number
}) => api.get<DemographicsTimeseries[]>('/demographics/timeseries', { params, paramsSerializer: { indexes: null } }).then(r => r.data)

export const fetchDemographicsSummary = (params: {
  year?: number
  region_id?: number
}) => api.get<DemographicsSummary>('/demographics/summary', { params }).then(r => r.data)

export const fetchMapGeoJSON = (params: {
  level?: 'region' | 'municipality'
  region_id?: number
  metric?: 'population' | 'change_percent'
  year?: number
  year_from?: number
  year_to?: number
}) => api.get('/map/geojson', { params }).then(r => r.data)

export const fetchMapDensity = (params: { year?: number }) =>
  api.get('/map/density', { params }).then(r => r.data)
