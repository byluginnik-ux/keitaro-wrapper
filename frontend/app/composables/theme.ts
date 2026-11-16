import { ref } from 'vue'

export type ThemeMode = 'system' | 'light' | 'dark'

export const THEME_KEY = 'theme-mode'
const ORDER: ThemeMode[] = ['system', 'light', 'dark']
export const THEME_LABELS: Record<ThemeMode, string> = {
  system: 'как в системе',
  light: 'светлая',
  dark: 'тёмная',
}

/** Runs before the first paint, so a chosen theme does not flash the other one (R-UX-20). */
export const THEME_BOOT_SCRIPT = `try{var m=localStorage.getItem('${THEME_KEY}');if(m==='light'||m==='dark')document.documentElement.dataset.mode=m}catch(e){}`

function stored(): ThemeMode {
  try {
    const value = localStorage.getItem(THEME_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  }
  catch {
    return 'system'
  }
}

function apply(mode: ThemeMode) {
  if (mode === 'system') delete document.documentElement.dataset.mode
  else document.documentElement.dataset.mode = mode
  try {
    if (mode === 'system') localStorage.removeItem(THEME_KEY)
    else localStorage.setItem(THEME_KEY, mode)
  }
  catch {
    // private mode: the choice lives until the page is closed
  }
}

/** The theme follows the system until the user picks one by hand. */
export function useThemeMode() {
  const mode = ref<ThemeMode>('system')

  function restore() {
    mode.value = stored()
  }

  function cycle() {
    mode.value = ORDER[(ORDER.indexOf(mode.value) + 1) % ORDER.length] ?? 'system'
    apply(mode.value)
  }

  return { mode, restore, cycle }
}
