import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function LandingPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-secondary">
      <Card className="w-full max-w-lg mx-4 shadow-xl">
        <CardHeader className="text-center">
          <CardTitle className="text-4xl font-bold tracking-tight">
            AI DevSecOps
          </CardTitle>
          <CardDescription className="text-lg">
            Security Assistant
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-center text-muted-foreground">
            Intelligent security analysis and DevSecOps automation powered by AI.
            Secure your pipelines, scan your code, and automate compliance.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 pt-4">
            <Button asChild className="flex-1" size="lg">
              <Link to="/login">Login</Link>
            </Button>
            <Button asChild className="flex-1" size="lg" variant="secondary">
              <Link to="/register">Register</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}