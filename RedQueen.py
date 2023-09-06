import json
import os
import random
import shutil
import threading
from typing import Optional

import time
from pathlib import Path
from random import randint

from core.ProjectAliceExceptions import SkillStartingFailed
from core.base.model.AliceSkill import AliceSkill
from core.commons import constants
from core.device.model.DeviceAbility import DeviceAbility
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler


class RedQueen(AliceSkill):

	def __init__(self):
		self._me = None
		self.chatterTimer: Optional[threading.Timer] = None
		super().__init__()


	def onStart(self):
		super().onStart()
		redQueenIdentityFile = self._getRedQueenIdentityFile()
		redQueenIdentityFileTemplate = redQueenIdentityFile.with_suffix(redQueenIdentityFile.suffix + '.dist')

		if redQueenIdentityFile.exists():
			self._me = json.loads(redQueenIdentityFile.read_text())
			if not self._me:
				self.logWarning('Red Queen identity file seems corrupted, rebuilding it')
				redQueenIdentityFile.unlink()

		if not redQueenIdentityFile.exists():
			if redQueenIdentityFileTemplate.exists():
				shutil.copyfile(str(redQueenIdentityFileTemplate), str(redQueenIdentityFile))
				self.logInfo('New Red Queen is born')
				self._me = json.loads(redQueenIdentityFile.read_text())
				self._me['infos']['born'] = time.strftime('%d.%m.%Y')
				self._saveRedQueenIdentity()
			else:
				raise SkillStartingFailed(skillName=self.name, error='Cannot find Red Queen identity template')
		else:
			self.logInfo('Found existing Red Queen identity')
			self._me = json.loads(redQueenIdentityFile.read_text())


	def onStop(self):
		self._saveRedQueenIdentity()
		super().onStop()


	def onBooted(self):
		self._decideStateOfMind()
		if self.getConfig('randomSpeaking'):
			self.randomlySpeak(init=True)


	def onSleep(self):
		self.UserManager.sleeping()


	def onWakeup(self):
		self.UserManager.wakeup()


	@property
	def mood(self) -> str:
		if self._me:
			return self._me['infos']['mood']
		else:
			return constants.UNKNOWN


	@staticmethod
	def _getRedQueenIdentityFile() -> Path:
		return Path(os.path.dirname(__file__), 'redQueen.json')


	def _saveRedQueenIdentity(self):
		file = self._getRedQueenIdentityFile()
		if not file.exists():
			self.logWarning('Red Queen identity file is not existing, cannot save current state')
			return

		file.write_text(json.dumps(self._me, indent='\t', sort_keys=False))


	def onQuarterHour(self):
		if not self.UserManager.checkIfAllUser('sleeping'):
			self.changeRedQueenStat('tiredness', 1)
			self.changeRedQueenStat('boredom', 2)
			self.changeRedQueenStat('happiness', -1)
		else:
			self.changeRedQueenStat('tiredness', -2)
			self.changeRedQueenStat('boredom', -2)
			self.changeRedQueenStat('happiness', 1)
			self.changeRedQueenStat('anger', -2)
			self.changeRedQueenStat('frustration', -2)


	def onFiveMinute(self):
		self._me['infos']['mood'] = self._decideStateOfMind()
		self._saveRedQueenIdentity()


	def onSessionEnded(self, session: DialogSession):
		if 'input' not in session.payload:
			return

		self.changeRedQueenStat('boredom', -2)
		self.changeRedQueenStat('frustration', -1)

		beenPolite = self.politnessUsed(session.payload['input'])
		if beenPolite:
			self.changeRedQueenStat('happiness', 4)
			self.changeRedQueenStat('anger', -4)
			self.changeRedQueenStat('frustration', -2)

			if self.mood == 'Anger':
				chance = 85
			elif self.mood == 'Tiredness':
				chance = 20
			elif self.mood == 'Boredom':
				chance = 50
			elif self.mood == 'Frustration':
				chance = 10
			else:
				chance = 25

			if randint(0, 100) < chance:
				self.say(text=self.randomTalk('thanksForBeingNice'), deviceUid=session.deviceUid)


	def politnessUsed(self, text: str) -> bool:
		self.logInfo(f'Checking if you were nice{text}')
		forms = self.LanguageManager.getStrings(key='politness', skill='system')

		for form in forms:
			if form not in text:
				continue

			return True

		return False


	def onUserCancel(self, session: DialogSession):
		self.changeRedQueenStat('frustration', 2)


	def inTheMood(self, session: DialogSession) -> bool:
		if self.getConfig(key='disableMoodTraits'):
			return True

		if self.mood == 'Anger':
			chance = 40
		elif self.mood == 'Tiredness':
			chance = 20
		elif self.mood == 'Boredom':
			chance = 10
		elif self.mood == 'Frustration':
			chance = 15
		else:
			chance = 2

		if random.randint(0, 100) < chance:
			self.endDialog(session.sessionId, self.randomTalk('noInTheMood'))
			return False

		return True


	@IntentHandler('WhoAreYou')
	def whoIntent(self, session: DialogSession):
		self.endDialog(sessionId=session.sessionId, text=self.randomTalk('aliceInfos'), deviceUid=session.deviceUid)


	@IntentHandler('GoodMorning')
	def morningIntent(self, session: DialogSession):
		self.broadcast(method=constants.EVENT_WAKEUP, exceptions=[constants.DUMMY], propagateToSkills=True)
		time.sleep(0.5)
		self.endDialog(sessionId=session.sessionId, text=self.randomTalk('goodMorning'), deviceUid=session.deviceUid)


	@IntentHandler('GoodNight')
	def nightIntent(self, session: DialogSession):
		self.endDialog(sessionId=session.sessionId, text=self.randomTalk('goodNight'), deviceUid=session.deviceUid)
		self.broadcast(method=constants.EVENT_SLEEP, exceptions=[constants.DUMMY], propagateToSkills=True)


	@IntentHandler('ChangeUserState')
	def userStateIntent(self, session: DialogSession):
		slots = session.slotsAsObjects

		if 'State' not in slots.keys():
			self.logError('No state provided for changing user state')
			self.endDialog(sessionId=session.sessionId, text=self.TalkManager.randomTalk('error', skill='system'),
			               deviceUid=session.deviceUid)
			return

		# Todo re enable this if statement when the "personDesignation" code gets fully implemented
		# if not 'Who' in slots.keys():
		try:
			self.broadcast(method=slots['State'][0].value['value'], exceptions=[constants.DUMMY], propagateToSkills=True)

		except:
			self.logWarning(f"Unsupported user state \"{slots['State'][0].value['value']}\"")

		self.endDialog(sessionId=session.sessionId, text=self.TalkManager.randomTalk(slots['State'][0].value['value']),
		               deviceUid=session.deviceUid)


	def randomlySpeak(self, init: bool = False):
		if not self.getConfig('randomSpeaking'):
			return

		mini = self.getConfig('randomTalkMinDelay')
		maxi = self.getConfig('randomTalkMaxDelay')

		if self.mood == 'Anger':
			maxi /= 3
		elif self.mood == 'Tiredness' or self.mood == 'Boredom':
			mini /= 2
			maxi /= 2
		elif self.mood == 'Frustrated':
			maxi /= 2

		if not init and not self.UserManager.checkIfAllUser('goingBed') and not self.UserManager.checkIfAllUser('sleeping'):
			devices = self.DeviceManager.getDevicesWithAbilities([DeviceAbility.PLAY_SOUND])
			if devices:
				self.say(self.randomTalk(f'randomlySpeak{self.mood}'), deviceUid=random.choice(devices).uid)

		rnd = random.randint(mini, maxi)
		self.chatterTimer = self.ThreadManager.newTimer(interval=rnd, func=self.randomlySpeak)
		self.logInfo(f'Scheduled next random speaking in {rnd} seconds')


	def changeRedQueenStat(self, stat: str, amount: int):
		if stat not in self._me['stats']:
			self.logWarning(f'Asked to change stat {stat} but it does not exist')
			return

		self._me['stats'][stat] += amount
		if self._me['stats'][stat] < 0:
			self._me['stats'][stat] = 0
		elif self._me['stats'][stat] > 100:
			self._me['stats'][stat] = 100


	def _decideStateOfMind(self) -> str:
		# TODO Algorythm for weighting the 5 stats
		stats = {
			'Anger'      : self._me['stats']['anger'] * 5,
			'Tiredness'  : self._me['stats']['tiredness'] * 4,
			'Happiness'  : self._me['stats']['happiness'] * 3,
			'Frustration': self._me['stats']['frustration'] * 2,
			'Boredom'    : self._me['stats']['boredom']
		}

		return self.Commons.dictMaxValue(stats)


	def getMoodValue(self, mood: str):
		if self._me:
			return self._me['stats'][mood]
		else:
			return constants.UNKNOWN


	def onHotword(self, deviceUid: str, user: str = constants.UNKNOWN_USER):
		self.onWakeword(deviceUid=deviceUid, user=user)


	def onWakeword(self, deviceUid: str, user: str = constants.UNKNOWN_USER):
		if not self.chatterTimer:
			return

		self.chatterTimer.cancel()
		self.chatterTimer = None
		self.randomlySpeak(init=True)

