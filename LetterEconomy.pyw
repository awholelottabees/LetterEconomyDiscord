import discord
import random
from datetime import datetime, timedelta, timezone
import time
import csv
import matplotlib.pyplot as plt
import os

intents = discord.Intents(messages=True)

client = discord.Client(intents=discord.Intents.all())

serverId = #PUT YOUR SERVER ID HERE
managerId = #PUT YOUR DISCORD USER ID HERE
maxLetters = 15 #CHANGE TO BE HOW MANY OF EACH LETTER SHOULD BE IN CIRCULATION
tradingChannel = #PUT THE ID OF WHAT CHANNEL TO TRADE IN HERE (bot channel)


currStockMkt = {}
ovnChange = {}
ownedLetters = {}
distributedLetters = {}
seed = {}
currDate = 0

###
#On member join, give them a new entry in ownedLetters and seed, set their starting fund to 30, and set their nickname to be empty
###
@client.event 
async def on_member_join(member):
    global ownedLetters
    global seed
    await member.edit(nick=".")
    ownedLetters[member.id] = ""
    seed[member.id] = 30.0
    saveToCsv()

@client.event
async def on_ready():
    print("Confirmed")

###
#Stocks are calculated at 8:00 AM, 12:00 PM, and 4:00 PM EST.
#This function calculates how many times stocks should update since the last time they were updated.
###
def numUpdate(past,now):
    days = (now-past).days
    now = now - timedelta(days=days)
    rollOver = False
    if(now.day != past.day):
        rollOver = True
    hours = 0
    if(now.hour >= 12 and (past.hour < 12 or rollOver)):
        hours += 1
    if(now.hour >= 16 and (past.hour < 16 or rollOver)):
        hours += 1
    if(now.hour >= 20 and (past.hour < 20 or rollOver)):
        hours += 1
    return ((3*days) + hours)

@client.event
async def on_message(message):
    print(str(message.author.id) + " - " + message.content)
    global currStockMkt
    global ovnChange
    global ownedLetters
    global distributedLetters
    global seed
    global currDate
    global serverId
    global managerId
    global maxLetters
    global tradingChannel
    dt = datetime.now(timezone.utc)
    if(currDate == 0):
        print("Setting Initial Date")
        updateStocks()
    else:
        numIter = numUpdate(currDate,dt)
        print(numIter)
        if(numIter > 0):
            for x in range(1,numUpdate(currDate,dt) + 1):
                updateStocks()
    currDate = dt

    if(message.channel.id != tradingChannel):
        return False
    
    guild = client.get_guild(serverId)

    #Print the commands of this bot
    if(message.content == "le!commands"):
        await message.channel.send("le!buy [letter] - invest in a letter\nle!sell [letter] - sell a letter\nle!change [nickname] - change your nickname\nle!netWorth - Check your balance\nle!letters - check your letters\nle!letters[user] - check someone elses letters\nle!leaderboard - compare your net worth to others\nle!currPrices - check current prices\nle!graph [letter/\"all\"] - check past stock prices")

    #The manager may force a save of data in the case of needing to restart the bot
    if(message.author.id == managerId and message.content == "le!save"):
        saveToCsv()
        await message.delete()

    #The manager may force the stocks to update
    if(message.author.id == managerId and message.content == "le!update"):
        await message.delete()
        print("updating...")
        updateStocks()

    #Print everyone's current net worth in order
    if(message.content == "le!leaderboard"):
        lboard = {}
        lstring = ""
        for member in guild.members:
            if(not member.bot):
                lboard[member] = round(netWorth(member.id),3)
        sortByWorth = {k : v for k, v in sorted(lboard.items(),reverse=True,key=lambda item: item[1])}
        for member, worth in sortByWorth.items():
            lstring += member.name
            lstring += " --- "
            lstring += str(worth)
            lstring += "\n"
        await message.channel.send(lstring)

    #Print the stock history of either a single letter or all letters
    if("le!graph" in message.content):
        command = message.content.split(" ")
        letter = command[1].lower()
        if(len(letter)) == 1:
            makeGraph(letter)
            await message.channel.send(file=discord.File("datapics/" + letter + 'data.png'))
        if(letter == "all"):
            makeGraphAll()
            await message.channel.send(file=discord.File("datapics/alldata.png"))

    #Buy a letter
    if("le!buy" in message.content and not message.author.bot):
        command = message.content.split(" ")
        letter = command[1].lower()
        if(len(letter)) == 1:
            if(buyLetter(message.author.id,letter)):
                await message.channel.send("You have successfully purchased a stock in " + letter)
            else:
                print(distributedLetters[letter])
                if(distributedLetters[letter] == maxLetters):
                    await message.channel.send("There are no more of that stock available")
                else:
                    await message.channel.send("You do not have the funds to do that")

    #Sell a letter
    if("le!sell" in message.content and not message.author.bot):
        command = message.content.split(" ")
        letter = command[1].lower()
        if(len(letter)) == 1:
            if(sellLetter(message.author.id,letter)):
                await message.channel.send("You have successfully sold a stock in " + letter)
                if(not confirmLetters(message.author.nick.lower(),ownedLetters[message.author.id].lower())):
                    try:
                        await message.author.edit(nick=".")
                    except:
                        await message.channel.send("Your nickname is now invalid")
            else:
                await message.channel.send("You do not have that letter to sell")

    #Print your letters, or if you include a mention, print the letters of someone else
    if(message.content == "le!letters"):
        await message.channel.send("You own the following letters: " + ownedLetters[message.author.id])
    elif("le!letters" in message.content):
        command = message.content.split(" ")
        person = command[1].replace("<@","").replace(">","")
        person = guild.get_member(int(person))
        await message.channel.send("<@" + str(person.id) + "> owns the following letters: " + ownedLetters[person.id])

    #Get your current net worth
    if(message.content == "le!netWorth"):
        await message.channel.send("Net Worth: " + str(round(netWorth(message.author.id),3)) + " with " + str(round(currCash(message.author.id),3)) + " currently liquid")

    #Set up the server, run initially to set up
    #WARNING: THIS WILL RESET ALL STOCK DATA AND LETTERS
    if(message.author.id == managerId and message.content == "le!init"):
        print("Yes")
        await message.delete()
        with open("currStuff.csv", "x") as stuffFile:
            print("User stats created")
        with open("stockMarket.csv","x") as stockFile:
            print("Stock file created")
        with open('stockData.csv','w+',newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow("abcdefghijklmnopqrstuvwxyz")
        os.mkdir("datapics")
        for member in guild.members:
            if(not member.bot):
                try:
                    await member.edit(nick=".")
                except:
                    print("admin")
                ownedLetters[member.id] = ""
                seed[member.id] = 30

        for letter in "abcdefghijklmnopqrstuvwxyz":
            currStockMkt[letter] = 2.5
            if(letter in "aeiou"):
                currStockMkt[letter] = 5
            ovnChange[letter] = 1
            distributedLetters[letter] = 0
        saveToCsv()

    #Change your nickname based on the letters you have
    #Admins cannot have their name changed. If an admin runs this command,
    #it will simply tell them if the nickname they input is possible given their
    #owned letters
    if("le!change" in message.content and not message.author.bot):
        command = message.content.split(" ")

        nick = message.content.replace("le!change ","",1)
        if(confirmLetters(nick.lower(),ownedLetters[message.author.id].lower())):
            try:
                await message.author.edit(nick=nick)
                await message.channel.send("Your nickname has been changed!")
            except:
                await message.channel.send("That is a valid nickname for you, but I cannot change it")
        else:
            await message.channel.send("You do not own the letters for this nickname!")

    #Get the current prices of each letter
    if(message.content == "le!currPrices"):
        prices = ""
        for letter in currStockMkt:
            prices = prices + (letter.upper() + " --- " + str(round(currStockMkt[letter],3)) + "   (" + str(maxLetters-distributedLetters[letter]) + " left)\n")
        await message.channel.send(prices)


###
#Get the historical data for a single letter and output a graph of its stock price
###
def makeGraph(letter):
    x = []
    y = []
    iter = 1
    with open('stockData.csv','r',newline='') as csvfile:
        reader = csv.reader(csvfile,delimiter = ",")

        headings = next(reader)

        for row in reader:
            x.append(int(iter))
            iter += 1
            y.append(float(row[ord(letter) - 97]))
    plt.close()
    plt.plot(x,y)
    plt.xlabel("Number of updates")
    plt.ylabel("Stock Price")
    plt.title("Price Changes for " + letter.upper())
    plt.savefig("datapics/" + letter + "data.png")


###
#Get the historical data for EVERY letter and output a graph of all stock prices.
#WARNING: Looks horrible
###
def makeGraphAll():
    x = []
    letterData = [[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]]
    iter = 1
    with open('stockData.csv','r',newline='') as csvfile:
        reader = csv.reader(csvfile,delimiter = ",")
        headings = next(reader)

        for row in reader:
            x.append(int(iter))
            iter += 1
            for i in range(0,26):
                letterData[i].append(float(row[i]))
    plt.close()
    plt.figure(figsize=(14,7))
    for i in range(0,26):
        plt.plot(x,letterData[i], label = str(chr(i + 97)))
    plt.xlabel("Number of updates")
    plt.ylabel("Stock Price")
    plt.title("Price Changes for all")
    plt.legend()
    plt.savefig("datapics/alldata.png")
    plt.close()


###
#Check to make sure that someone's ideal nickname and their letters match
###
def confirmLetters(nick,letters):
    word = nick
    for letter in letters:
        word = word.replace(letter,'',1)
        print(word)
        if(len(word) == 0):
            return True
    if(len(word) == 0):
        return True
    for letter in word:
        if(letter.isalpha()):
            return False
    return True

###
#The totally legitimate stock market function. Includes more detail that I should have put in here.
###
def updateStocks():
    avg = 0.0
    for key in ovnChange: 
        avg += float(ovnChange[key])
    avg = avg / 26.0   #The average multiplier for all 26 letters over the past change.
    data = []
    for key in currStockMkt: #For each letter
        pastPrice = currStockMkt[key]  #Get its past price
        pastChange = ovnChange[key]  #and its past change
        futureChange = 0
        x = random.randint(1,100) #Stocks have a chance to surge in price.
        if(key in "aeiou"): #Vowels are more volatile
            x = random.randint(1,10)  #So they are more likely to surge
        y = random.randint(1,70) #There is also a chance to crash
        if(y == 1): #A 1 in 70 chance to be precise
            print("crash")
            futureChange = 0.1
        elif(x == 2): #WIth a 1 in 100 chance to surge.
            print("surge")
            futureChange = 3
        elif(y < 9 and key in "aeiou"): #Vowels also have a chance for a MAJOR crash
            print("major crash")
            futureChange = 0.01
        else: #But if they don't surge or crash, we move on.
            if(pastChange > 1.7 * avg): #If they had an above average increase/decrease, it's trending up!
                futureChange = random.uniform(0.7, 1.7) #They can't go below 0.7,
                if(futureChange > 1.5): #And have a higher chance of hitting 1.5!
                    futureChange = 1.5
            elif(pastChange < 0.6 * avg): #If they had a below average increase/decrease, it's trending down!
                futureChange = random.uniform(0.3,1.3) #They can't go above 1.3
                if(futureChange < 0.5): #And have a higher chance of hitting 0.5!
                    futureChange = 0.5
            else: #Otherwise
                futureChange = random.uniform(0.5,1.5) #We get an even spread of possibilities.
        futureChange = round(futureChange, 3)
        print(futureChange)
        newPrice = round(pastPrice * futureChange,3) #We set their new price,
        if(newPrice <= 0.7): #But if their new price is too low,
            if(key in "aeiou"): #We set vowels back to 2.5
                newPrice = 2.5
            if(newPrice > 0.1): #And give non-vowels the chance to bounce back up to 0.7
                z = random.uniform(1.0,newPrice * 10) #proportional to how low the price is
                if(z < 2):
                    newPrice = 0.7
            else: #And if it gets somehow below 0.1, we bump it back to 0.5
                newPrice = 0.5
        if(newPrice > 25 and letter not in "aeiou"): #But non-vowels have a price cap! If they get too high...
            newPrice = random.uniform(2.0,6.0) #The bubble bursts! They go to a random lower price.
        currStockMkt[key] = newPrice
        ovnChange[key] = futureChange
        data.append(newPrice)
    with open('stockData.csv','a',newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(data)
    saveToCsv()

###
#Buy a letter! Includes detail as well.
###
def buyLetter(pid, letter):
    global currStockMkt
    global ownedLetters
    global distributedLetters
    global seed

    if(currStockMkt[letter] < seed[pid] and distributedLetters[letter] < maxLetters): #If you have the funds for that letter...
        distributedLetters[letter] = distributedLetters[letter] + 1 #Congrats! It's yours.
        seed[pid] = seed[pid] - currStockMkt[letter] #You pay for it
        ownedLetters[pid] = ownedLetters[pid] + letter #You own it
        currStockMkt[letter] = currStockMkt[letter] + 0.1 #And there's more demand, so the price has gone up!
        return True #Congrats!
        saveToCsv()
    else:
        return False
    
###
#Sell a letter (with new detail!!!)
###
def sellLetter(pid, letter):
    global currStockMkt
    global ownedLetters
    global distributedLetters
    global seed
    if(letter in ownedLetters[pid]): #If you own a letter
        currStockMkt[letter] = currStockMkt[letter] - 0.11 #Unfortunately, you can't cheat the system by buying and selling repeatedly. To sell a stock, the market takes a fee of 0.11.
        distributedLetters[letter] = distributedLetters[letter] - 1 #The letter returns to the market
        seed[pid] = seed[pid] + currStockMkt[letter] #And you get paid!
        ownedLetters[pid] = ownedLetters[pid].replace(letter,'',1)  #And you lose the letter!
        currStockMkt[letter] = currStockMkt[letter] + 0.01 #And the price is reduced by a net of 0.1
        if(currStockMkt[letter] < 0.1): #If you're selling this low, that's on you...
            currStockMkt[letter] = 0.1
        saveToCsv()
        return True
    else:
        return False

###
#Net Worth calculator for a given person
###
def netWorth(pid):
    global ownedLetters
    global seed
    worth = 0.0
    for letter in ownedLetters[pid]:
        worth = worth + currStockMkt[letter]
    return worth + seed[pid]

###
#Internal only
###
def currCash(pid):
    global seed
    return seed[pid]


###
#Automatically run, loads data from csv in the case of resets.
###
def loadFromCsv():
    global currStockMkt
    global ovnChange
    global ownedLetters
    global distributedLetters
    global seed

    with open('stockmarket.csv','r',newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter = ",")

        headings = next(reader)

        for row in reader:
            letter = row[0]
            currPrice = float(row[1])
            lChange = float(row[2])
            numdist = int(row[3])
            currStockMkt[letter] = currPrice
            ovnChange[letter] = lChange
            distributedLetters[letter] = numdist
    with open('currStuff.csv', 'r', newline='') as csvfile:
        reader = csv.reader(csvfile,delimiter=",")

        headings = next(reader)
        for row in reader:
            pid = int(row[0])
            currLett = row[1]
            fund = float(row[2])
            ownedLetters[pid] = currLett
            seed[pid] = fund

###
#Automatically or Manually run, saves all data to csvs.
###
def saveToCsv():
    global currStockMkt
    global ovnChange
    global ownedLetters
    global distributedLetters
    global seed

    with open('stockmarket.csv','w',newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['letter','currprice','lastchange','numdistributed'])
        for key in currStockMkt:
            writer.writerow([key,currStockMkt[key],ovnChange[key],distributedLetters[key]])
    with open('currStuff.csv','w',newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['person','ownedletters','fund'])
        for key in seed:
            writer.writerow([key,ownedLetters[key],seed[key]])

loadFromCsv()
client.run() #INSERT BOT TOKEN HERE
