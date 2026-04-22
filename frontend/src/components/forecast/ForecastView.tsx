import { useState } from 'react'
import { Card, Select, Slider, Button, Row, Col, Table, Empty, message } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchRegions, fetchMunicipalitiesByRegion } from '@/api/population'
import { generateForecast, type ForecastResponse } from '@/api/forecast'
import { formatNumber } from '@/utils/formatters'

export default function ForecastView() {
  const [regionId, setRegionId] = useState<number | null>(null)
  const [municipalityId, setMunicipalityId] = useState<number | null>(null)
  const [horizon, setHorizon] = useState(10)
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null)

  const { data: regions = [] } = useQuery({
    queryKey: ['regions'],
    queryFn: fetchRegions,
  })

  const { data: municipalities = [] } = useQuery({
    queryKey: ['municipalities', regionId],
    queryFn: () => fetchMunicipalitiesByRegion(regionId!),
    enabled: !!regionId,
  })

  const mutation = useMutation({
    mutationFn: () => generateForecast(municipalityId!, horizon),
    onSuccess: (data) => setForecastData(data),
    onError: () => message.error('Ошибка генерации прогноза'),
  })

  const chartOption = forecastData
    ? {
        tooltip: { trigger: 'axis' as const },
        legend: { top: 0 },
        grid: { left: 70, right: 30, top: 50, bottom: 30 },
        xAxis: {
          type: 'category' as const,
          data: [
            ...forecastData.historical.map((h) => h.year),
            ...forecastData.forecast.map((f) => f.year),
          ],
          axisLabel: { interval: 2 },
        },
        yAxis: {
          type: 'value' as const,
          axisLabel: {
            formatter: (val: number) =>
              val >= 1_000_000 ? `${(val / 1_000_000).toFixed(1)}М` : `${(val / 1_000).toFixed(0)}К`,
          },
        },
        series: [
          {
            name: 'Факт',
            type: 'line',
            data: [
              ...forecastData.historical.map((h) => h.population),
              ...forecastData.forecast.map(() => null),
            ],
            lineStyle: { width: 3, color: '#2b6cb0' },
            itemStyle: { color: '#2b6cb0' },
            smooth: true,
          },
          {
            name: 'Прогноз',
            type: 'line',
            data: [
              ...forecastData.historical.map(() => null),
              ...forecastData.forecast.map((f) => f.predicted_population),
            ],
            lineStyle: { width: 3, type: 'dashed' as const, color: '#d69e2e' },
            itemStyle: { color: '#d69e2e' },
            smooth: true,
          },
          {
            name: 'Доверительный интервал',
            type: 'line',
            data: [
              ...forecastData.historical.map(() => null),
              ...forecastData.forecast.map((f) => f.confidence_upper),
            ],
            lineStyle: { width: 0 },
            itemStyle: { color: 'transparent' },
            stack: 'ci',
            symbol: 'none',
          },
          {
            name: 'CI нижняя',
            type: 'line',
            data: [
              ...forecastData.historical.map(() => null),
              ...forecastData.forecast.map((f) => f.confidence_lower),
            ],
            lineStyle: { width: 0 },
            itemStyle: { color: 'transparent' },
            areaStyle: { color: '#d69e2e', opacity: 0.15 },
            stack: 'ci',
            symbol: 'none',
          },
        ],
        animationDuration: 1000,
      }
    : null

  const tableData = forecastData?.forecast.map((f) => ({
    key: f.year,
    year: f.year,
    predicted: f.predicted_population,
    lower: f.confidence_lower,
    upper: f.confidence_upper,
  }))

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col xs={24} sm={8}>
            <Select
              placeholder="Регион"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
              value={regionId}
              onChange={(val) => {
                setRegionId(val ?? null)
                setMunicipalityId(null)
                setForecastData(null)
              }}
              options={regions.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Col>
          <Col xs={24} sm={8}>
            <Select
              placeholder="Муниципалитет"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
              value={municipalityId}
              onChange={(val) => {
                setMunicipalityId(val ?? null)
                setForecastData(null)
              }}
              disabled={!regionId}
              options={municipalities.map((m) => ({ value: m.id, label: m.name }))}
            />
          </Col>
          <Col xs={24} sm={4}>
            <div style={{ fontSize: 12, color: '#718096' }}>Горизонт: {horizon} лет</div>
            <Slider min={5} max={15} value={horizon} onChange={setHorizon} />
          </Col>
          <Col xs={24} sm={4}>
            <Button
              type="primary"
              icon={<LineChartOutlined />}
              onClick={() => mutation.mutate()}
              loading={mutation.isPending}
              disabled={!municipalityId}
              block
            >
              Прогноз
            </Button>
          </Col>
        </Row>
      </Card>

      {forecastData && chartOption ? (
        <>
          <Card
            title={`Прогноз: ${forecastData.municipality_name}`}
            style={{ marginBottom: 16 }}
          >
            <ReactECharts option={chartOption} style={{ height: 400 }} />
          </Card>
          <Card title="Прогнозные значения" size="small">
            <Table
              dataSource={tableData}
              pagination={false}
              size="small"
              columns={[
                { title: 'Год', dataIndex: 'year', key: 'year' },
                {
                  title: 'Прогноз',
                  dataIndex: 'predicted',
                  key: 'predicted',
                  render: (v: number) => <strong>{formatNumber(v)}</strong>,
                },
                {
                  title: 'Нижняя граница',
                  dataIndex: 'lower',
                  key: 'lower',
                  render: (v: number | null) => formatNumber(v),
                },
                {
                  title: 'Верхняя граница',
                  dataIndex: 'upper',
                  key: 'upper',
                  render: (v: number | null) => formatNumber(v),
                },
              ]}
            />
          </Card>
        </>
      ) : (
        <Card>
          <Empty description="Выберите муниципалитет и нажмите 'Прогноз'" />
        </Card>
      )}
    </div>
  )
}
