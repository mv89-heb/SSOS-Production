

# SSOS Migration Map


## Backend

Current:

app/models
app/routes
app/services
app/repositories


Target:

backend/app/models
backend/app/routes
backend/app/services
backend/app/repositories



## Frontend

Current:

frontend/src/app/dashboard
frontend/src/app/login


Target:

frontend/src/app/[locale]/dashboard
frontend/src/app/[locale]/login



## Migration Order


1. Backup
2. Baseline tests
3. Backend alignment
4. Frontend routing
5. Authentication
6. API contract
7. Deployment validation


