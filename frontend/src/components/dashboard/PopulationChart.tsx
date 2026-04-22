import { Card, Empty } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchPopulationTimeseries } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'
import { CHART_COLORS } from '@/utils/colors'

export default function PopulationChart() {
  const { municipalityId, regionId, yearFrom, yearTo } = useFilterStore()

  const { data: timeseries = [], isLoading } = useQuery({
    queryKey: ['populationTimeseries', municipalityId, regionId, yearFrom, yearTo],
    queryFn: () => {
      if (municipalityId) {
        return fetchPopulationTimeseries({ municipality_id: [municipalityId], year_from: yearFrom, year_to: yearTo })
      }
      return []
    },
    enabled: !!municipalityId,
  })

  if (!municipalityId) {
    return (
      <Card title="Динамика населения" style={{ marginBottom: 16 }}>
        <Empty description="Выберите муниципалитет для отображения графика" />
      </Card>
    )
  }

  const option = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        let html = `<strong>${params[0]?.axisValue}</strong><br/>`
        params.forEach((p: any) => {
          html += `${p.marker} ${p.seriesName}: ${p.value?.toLocaleString('ru-RU') ?? '—'} чел.<br/>`
        })
        return html
      },
    },
    grid: { left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: timeseries[0]?.data.map((d) => d.year) ?? [],
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (val: number) =>
          val >= 1_000_000 ? `${(val / 1_000_000).toFixed(1)}М` : val >= 1_000 ? `${(val / 1_000).toFixed(0)}К` : val,
      },
    },
    series: timeseries.map((ts, i) => ({
      name: ts.municipality_name,
      type: 'line',
      data: ts.data.map((d) => d.population),
      smooth: true,
      lineStyle: { width: 3 },
      itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: CHART_COLORS[i % CHART_COLORS.length] + '40' },
            { offset: 1, color: CHART_COLORS[i % CHART_COLORS.length] + '05' },
          ],
        },
      },
    })),
    animationDuration: 800,
  }

  return (
    <Card title="Динамика населения" loading={isLoading} style={{ marginBottom: 16 }}>
      <ReactECharts option={option} style={{ height: 350 }} />
    </Card>
  )
}
