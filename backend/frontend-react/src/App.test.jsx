import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

describe('App', () => {
  it('renders loading spinner initially', () => {
    renderWithRouter(<App />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})