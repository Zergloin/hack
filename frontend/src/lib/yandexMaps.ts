const YANDEX_MAPS_SCRIPT_ID = 'yandex-maps-js-api-v3'
const YANDEX_MAPS_SCRIPT_URL = 'https://api-maps.yandex.ru/v3/'
const YANDEX_LOAD_ERROR =
  'Failed to load Yandex Maps API. Check network access to api-maps.yandex.ru, ensure the key is active, and allow the page origin in HTTP Referer restrictions.'

let ymapsPromise: Promise<typeof ymaps3> | null = null

export function loadYandexMapsApi(apiKey: string) {
  if (!apiKey) {
    return Promise.reject(new Error('Yandex Maps API key is missing'))
  }

  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Yandex Maps API can only be loaded in the browser'))
  }

  if (window.ymaps3) {
    return window.ymaps3.ready.then(() => window.ymaps3 as typeof ymaps3)
  }

  if (ymapsPromise) {
    return ymapsPromise
  }

  ymapsPromise = new Promise<typeof ymaps3>((resolve, reject) => {
    const existingScript = document.getElementById(YANDEX_MAPS_SCRIPT_ID) as HTMLScriptElement | null

    const handleReady = () => {
      if (!window.ymaps3) {
        reject(new Error('Yandex Maps API script loaded, but ymaps3 is unavailable'))
        return
      }

      window.ymaps3.ready
        .then(() => resolve(window.ymaps3 as typeof ymaps3))
        .catch(reject)
    }

    if (existingScript) {
      if (window.ymaps3) {
        handleReady()
        return
      }

      existingScript.addEventListener('load', handleReady, { once: true })
      existingScript.addEventListener(
        'error',
        () => reject(new Error(YANDEX_LOAD_ERROR)),
        { once: true }
      )
      return
    }

    const script = document.createElement('script')
    script.id = YANDEX_MAPS_SCRIPT_ID
    script.src = `${YANDEX_MAPS_SCRIPT_URL}?apikey=${encodeURIComponent(apiKey)}&lang=ru_RU`
    script.async = true
    script.onload = handleReady
    script.onerror = () => reject(new Error(YANDEX_LOAD_ERROR))
    document.head.appendChild(script)
  }).catch((error) => {
    ymapsPromise = null
    console.error('Yandex Maps API load failed', error)
    throw error
  })

  return ymapsPromise
}
