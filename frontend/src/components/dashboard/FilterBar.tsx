import { Select, Slider, Space, Card } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { fetchRegions, fetchMunicipalitiesByRegion } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'

export default function FilterBar() {
  const { regionId, municipalityId, yearFrom, yearTo, setRegionId, setMunicipalityId, setYearRange } =
    useFilterStore()

  const { data: regions = [] } = useQuery({
    queryKey: ['regions'],
    queryFn: fetchRegions,
  })

  const { data: municipalities = [] } = useQuery({
    queryKey: ['municipalities', regionId],
    queryFn: () => fetchMunicipalitiesByRegion(regionId!),
    enabled: !!regionId,
  })

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space wrap size="middle">
        <Select
          placeholder="Регион"
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ width: 280 }}
          value={regionId}
          onChange={(val) => setRegionId(val ?? null)}
          options={regions.map((r) => ({ value: r.id, label: r.name }))}
        />
        <Select
          placeholder="Муниципалитет"
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ width: 280 }}
          value={municipalityId}
          onChange={(val) => setMunicipalityId(val ?? null)}
          disabled={!regionId}
          options={municipalities.map((m) => ({ value: m.id, label: m.name }))}
        />
        <div style={{ width: 280 }}>
          <span style={{ fontSize: 12, color: '#718096' }}>
            Период: {yearFrom} — {yearTo}
          </span>
          <Slider
            range
            min={2010}
            max={2022}
            value={[yearFrom, yearTo]}
            onChange={([f, t]) => setYearRange(f, t)}
          />
        </div>
      </Space>
    </Card>
  )
}
