# ===============================
# Student Result Prediction ML
# ===============================

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# -------------------------------
# Step 1: Dataset
# -------------------------------
data = {
    'attendance': [85, 60, 90, 70, 40, 95, 55, 80, 65, 88],
    'assignment_marks': [18, 10, 19, 15, 8, 20, 12, 17, 14, 19],
    'mid_marks': [25, 18, 28, 22, 10, 30, 16, 24, 20, 27],
    'previous_result': [1, 0, 1, 1, 0, 1, 0, 1, 1, 1],
    'final_result': [1, 0, 1, 1, 0, 1, 0, 1, 1, 1]
}

df = pd.DataFrame(data)

print("Dataset:")
print(df)

# -------------------------------
# Step 2: Features & Target
# -------------------------------
X = df[['attendance', 'assignment_marks', 'mid_marks', 'previous_result']]
y = df['final_result']

# -------------------------------
# Step 3: Train Test Split
# -------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# -------------------------------
# Step 4: Train Model
# -------------------------------
model = LogisticRegression()
model.fit(X_train, y_train)

# -------------------------------
# Step 5: Model Evaluation
# -------------------------------
y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print("\nModel Accuracy:", accuracy)

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# -------------------------------
# Step 6: New Student Prediction
# -------------------------------
# Format: [attendance, assignment_marks, mid_marks, previous_result]
new_student = [[75, 16, 23, 1]]

prediction = model.predict(new_student)

print("\nNew Student Prediction:")
if prediction[0] == 1:
    print("Result: PASS")
else:
    print("Result: FAIL")