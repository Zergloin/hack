import { Button, Card, Segmented, Select, Slider, Space, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { fetchRegions, fetchMunicipalitiesByRegion } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'

const QUICK_RANGES = [
  { label: '5 лет', value: '5', range: [2018, 2022] as const },
  { label: '10 лет', value: '10', range: [2013, 2022] as const },
  { label: 'Весь период', value: 'all', range: [2010, 2022] as const },
]

export default function FilterBar() {
  const { regionId, municipalityId, yearFrom, yearTo, setRegionId, setMunicipalityId, setYearRange, resetFilters } =
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

  const quickRangeValue =
    QUICK_RANGES.find((item) => item.range[0] === yearFrom && item.range[1] === yearTo)?.value ?? 'custom'

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>Фильтры обзора</Typography.Text>
            <div style={{ fontSize: 12, color: '#718096' }}>
              Без выбора муниципалитета показывается агрегированный срез по региону или по России.
            </div>
          </div>
          <Button onClick={resetFilters}>Сбросить</Button>
        </div>

        <Space wrap size="middle" style={{ width: '100%' }}>
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
            style={{ width: 320 }}
            value={municipalityId}
            onChange={(val) => setMunicipalityId(val ?? null)}
            disabled={!regionId}
            options={municipalities.map((m) => ({ value: m.id, label: m.name }))}
          />
          <Segmented
            options={QUICK_RANGES.map((item) => ({ label: item.label, value: item.value }))}
            value={quickRangeValue === 'custom' ? undefined : quickRangeValue}
            onChange={(value) => {
              const selected = QUICK_RANGES.find((item) => item.value === value)
              if (selected) {
                setYearRange(selected.range[0], selected.range[1])
              }
            }}
          />
        </Space>

        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Typography.Text style={{ fontSize: 12, color: '#718096' }}>
              Период: {yearFrom} — {yearTo}
            </Typography.Text>
            {quickRangeValue === 'custom' && (
              <Typography.Text style={{ fontSize: 12, color: '#718096' }}>
                Пользовательский диапазон
              </Typography.Text>
            )}
          </div>
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
