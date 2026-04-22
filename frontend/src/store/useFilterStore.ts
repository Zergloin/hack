import { create } from 'zustand'

interface FilterState {
  regionId: number | null
  municipalityId: number | null
  yearFrom: number
  yearTo: number
  setRegionId: (id: number | null) => void
  setMunicipalityId: (id: number | null) => void
  setYearRange: (from: number, to: number) => void
}

export const useFilterStore = create<FilterState>((set) => ({
  regionId: null,
  municipalityId: null,
  yearFrom: 2010,
  yearTo: 2022,
  setRegionId: (id) => set({ regionId: id, municipalityId: null }),
  setMunicipalityId: (id) => set({ municipalityId: id }),
  setYearRange: (from, to) => set({ yearFrom: from, yearTo: to }),
}))
