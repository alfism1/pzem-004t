import http.client
import json
import pika
import os
from dotenv import load_dotenv

load_dotenv()


def is_stopkontak_active(stopkontak):
    conn = http.client.HTTPSConnection("ufatech.id")
    payload = json.dumps({
        "stopkontak": stopkontak
    })
    headers = {
        'Content-Type': 'application/json'
    }
    conn.request("GET", "/pln/api/get_stopkontak_by_id.php", payload, headers)
    res = conn.getresponse()
    data = res.read()

    try:
        result = json.loads(data.decode("utf-8"))
        return result["message"]["usage_status"] == "active"
    except Exception as e:
        return False


if __name__ == "__main__":
    queue_name = "payment_status"
    # Access the CLODUAMQP_URL environment variable and parse it (fallback to localhost)
    url = os.environ.get(
        'CLOUDAMQP_URL', os.getenv('RABBIT_MQ_URL'))
    params = pika.URLParameters(url)
    # params.heartbeat = 0
    # params.blocked_connection_timeout = 0
    while True:
        connection = pika.BlockingConnection(params)
        channel = connection.channel()  # start a channel
        channel.queue_declare(
            queue=queue_name, durable=True)  # Declare a queue

        def callback(ch, method, properties, body):
            decode = body.decode("utf-8")
            json_decoded = json.loads(decode)
            daya = json_decoded["daya_kwh"]
            stopkontak = json_decoded["stopkontak"]
            # check stop kontak status. If active don't process
            if not is_stopkontak_active(stopkontak):
                # pzem_reader.splu_process("/dev/ttyUSB0", 23, daya)
                pzem_cmd = ""
                if stopkontak == "stopkontak_0001":
                    pzem_cmd = "python3 pzem_reader.py /dev/ttyUSB0 23 " + \
                        str(daya) + " " + stopkontak + " &"
                elif stopkontak == "stopkontak_0002":
                    pzem_cmd = "python3 pzem_reader.py /dev/ttyUSB1 22 " + \
                        str(daya) + " " + stopkontak + " &"
                os.system(pzem_cmd)
            print(body)
            print(pzem_cmd)
            # ch.basic_ack(delivery_tag=method.delivery_tag)

        # # set up subscription on the queue
        # channel.basic_qos(prefetch_count=1)
        # channel.basic_consume(queue_name,
        #                       callback)
        channel.basic_consume(queue_name,
                              callback, auto_ack=True)

        try:
            print('[*] Waiting for messages.... To exit press CTRL+C')
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
            connection.close()
        except pika.exceptions.ConnectionClosedByBroker:
            # Uncomment this to make the example not attempt recovery
            # from server-initiated connection closure, including
            # when the node is stopped cleanly
            # except pika.exceptions.ConnectionClosedByBroker:
            #     pass
            continue
        except pika.exceptions.StreamLostError:
            continue
        finally:
            print("Restarted")
            continue
