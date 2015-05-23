#define D13 13

int adc;
char *pAdc;
int pwmLvl = 1;
int pwmStep = 0;
int pwmCntr = 0;
int pwmPin = D13;
bool isOn = false;

void setup() {
  pAdc = (char*)&adc;
  Serial.begin(57600);
  pinMode(D13, OUTPUT);
}

void loop() {
  adc = analogRead(A5);
  Serial.write(0xFF);
  Serial.write(pAdc, 2);
  if(Serial.available()) {
    pwmLvl = Serial.read();
  }
  if((pwmLvl > pwmStep) && !isOn) {
    digitalWrite(pwmPin, HIGH);
    isOn = true;
  } else if ((pwmLvl < pwmStep) && isOn) {
    digitalWrite(pwmPin, LOW);
    isOn = false;
  }
  if(++pwmCntr > 10) {
    pwmCntr = 0;
    pwmStep += 1;
  }
  if(pwmStep > 255) {
    pwmStep = 0;
  }
}


