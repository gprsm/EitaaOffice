import createCache from '@emotion/cache'
import { prefixer } from 'stylis'
import rtlPlugin from 'stylis-plugin-rtl'

export const rtlCache = createCache({
  key: 'eitaa-rtl',
  stylisPlugins: [prefixer, rtlPlugin],
})
