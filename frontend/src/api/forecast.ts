import api from './client'

export interface ForecastPoint {
  year: number
  predicted_population: number
  confidence_lower: number | null
  confidence_upper: number | null
}

export interface ForecastResponse {
  municipality_id: number
  municipality_name: string
  model_name: string
  historical: { year: number; population: number | null }[]
  forecast: ForecastPoint[]
}

export const generateForecast = (municipality_id: number, horizon_years: number) =>
  api.post<ForecastResponse>('/forecast/predict', { municipality_id, horizon_years }).then(r => r.data)

export const getForecast = (municipality_id: number) =>
  api.get<ForecastPoint[]>(`/forecast/${municipality_id}`).then(r => r.data)
