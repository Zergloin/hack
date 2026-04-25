import { useState } from 'react'
import { Card, Empty, Segmented, Space, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchPopulationTimeseries } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'
import { CHART_COLORS } from '@/utils/colors'

type PopulationChartMode = 'population' | 'change_absolute' | 'change_percent'

export default function PopulationChart() {
  const { municipalityId, regionId, yearFrom, yearTo } = useFilterStore()
  const [mode, setMode] = useState<PopulationChartMode>('population')

  const { data: timeseries = [], isLoading } = useQuery({
    queryKey: ['populationTimeseries', municipalityId, regionId, yearFrom, yearTo],
    queryFn: () => {
      if (municipalityId) {
        return fetchPopulationTimeseries({ municipality_id: [municipalityId], year_from: yearFrom, year_to: yearTo })
      }

      return fetchPopulationTimeseries({
        municipality_id: [],
        region_id: regionId ?? undefined,
        year_from: yearFrom,
        year_to: yearTo,
      })
    },
  })

  const series = timeseries[0]
  const years = series?.data.map((point) => point.year) ?? []
  const values = series?.data.map((point) => point.population) ?? []
  const changes = values.map((value, index) => {
    if (index === 0 || value == null || values[index - 1] == null) {
      return null
    }
    return value - (values[index - 1] as number)
  })
  const changePercents = values.map((value, index) => {
    const previousValue = values[index - 1]

    if (index === 0 || value == null || previousValue == null || previousValue === 0) {
      return null
    }

    return Number((((value - previousValue) / previousValue) * 100).toFixed(2))
  })
  const isChangeMode = mode !== 'population'
  const isPercentMode = mode === 'change_percent'

  const option = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        let html = `<strong>${params[0]?.axisValue}</strong><br/>`
        params.forEach((item: any) => {
          const formattedValue = item.value == null
            ? '—'
            : isPercentMode
              ? `${item.value > 0 ? '+' : ''}${Number(item.value).toFixed(2)}%`
              : Number(item.value).toLocaleString('ru-RU')
          const suffix = mode === 'population'
            ? ' чел.'
            : isPercentMode
              ? ' к прошлому году'
              : ' чел. к прошлому году'

          html += `${item.marker} ${item.seriesName}: ${formattedValue}${suffix}<br/>`
        })
        return html
      },
    },
    grid: { left: 60, right: 30, top: 50, bottom: 60 },
    dataZoom: [
      { type: 'inside' as const, start: 0, end: 100 },
      { type: 'slider' as const, bottom: 10, height: 18 },
    ],
    xAxis: {
      type: 'category' as const,
      data: years,
      boundaryGap: isChangeMode,
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (value: number) => {
          if (isPercentMode) {
            return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
          }

          if (mode === 'change_absolute') {
            return value >= 1_000 || value <= -1_000
              ? `${value > 0 ? '+' : ''}${(value / 1_000).toFixed(0)}К`
              : `${value > 0 ? '+' : ''}${value}`
          }

          return value >= 1_000_000
            ? `${(value / 1_000_000).toFixed(1)}М`
            : value >= 1_000
              ? `${(value / 1_000).toFixed(0)}К`
              : value
        },
      },
    },
    series: [
      mode === 'population'
        ? {
            name: series?.municipality_name || 'Население',
            type: 'line',
            data: values,
            smooth: true,
            lineStyle: { width: 3, color: CHART_COLORS[0] },
            itemStyle: { color: CHART_COLORS[0] },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: `${CHART_COLORS[0]}55` },
                  { offset: 1, color: `${CHART_COLORS[0]}08` },
                ],
              },
            },
            markLine: {
              symbol: 'none',
              data: [{ type: 'average', name: 'Среднее' }],
              lineStyle: { color: '#8c8c8c', type: 'dashed' },
            },
          }
        : {
            name: isPercentMode ? 'Изменение, % к прошлому году' : 'Изменение к прошлому году',
            type: 'bar',
            data: isPercentMode ? changePercents : changes,
            itemStyle: {
              color: (params: any) => (params.value >= 0 ? '#389e0d' : '#cf1322'),
              borderRadius: [6, 6, 0, 0],
            },
            markLine: {
              symbol: 'none',
              data: [{ yAxis: 0 }],
              lineStyle: { color: '#8c8c8c', type: 'dashed' },
            },
          },
    ],
    animationDuration: 800,
  }

  return (
    <Card
      style={{ marginBottom: 16 }}
      loading={isLoading}
      title="Динамика населения"
      extra={(
        <Space size="middle">
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {series?.municipality_name || 'Нет данных'}
          </Typography.Text>
          <Segmented
            size="small"
            options={[
              { label: 'Население', value: 'population' },
              { label: 'Изменение, чел.', value: 'change_absolute' },
              { label: 'Изменение, %', value: 'change_percent' },
            ]}
            value={mode}
            onChange={(value) => setMode(value as PopulationChartMode)}
          />
        </Space>
      )}
    >
      {series ? (
        <ReactECharts option={option} style={{ height: 360 }} />
      ) : (
        <Empty description="Данные по населению не найдены" />
      )}
    </Card>
  )
}
